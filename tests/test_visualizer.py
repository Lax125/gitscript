import unittest
from unittest.mock import Mock, patch

from gitscript.commands import branch, checkout, commit, reset
from gitscript.refs import ConstantOffsetRef, HeadRef
from gitscript.repo import Repo
from gitscript.visualizer import (
    GraphVisualizer,
    _commit_positions,
    _graph_data,
    _pyvis_edge,
    _pyvis_node,
    _visible_reachable_commits,
)


class VisualizerTests(unittest.TestCase):
    def test_positions_put_newer_commits_above_older_commits(self):
        repo = Repo()
        commit(repo, 1)
        commit(repo, 2)

        positions = _commit_positions(repo.commits)

        self.assertLess(positions[repo.commits[2]][1], positions[repo.commits[1]][1])
        self.assertLess(positions[repo.commits[1]][1], positions[repo.commits[0]][1])

    def test_positions_compact_after_filtered_commits_are_removed(self):
        repo = Repo()
        commit(repo, 1)
        first = repo.current_commit()
        for value in range(2, 82):
            commit(repo, value)
        newest = repo.current_commit()

        positions = _commit_positions([repo.commits[0], first, newest])

        self.assertEqual(positions[first][1] - positions[newest][1], 130)
        self.assertEqual(positions[repo.commits[0]][1] - positions[first][1], 130)

    def test_visible_reachable_commits_excludes_unreachable_commits(self):
        repo = Repo()
        commit(repo, 1)
        commit(repo, 2)
        orphaned = repo.current_commit()
        reset(repo, ConstantOffsetRef(HeadRef(), 1))

        reachable = _visible_reachable_commits(repo)

        self.assertNotIn(orphaned, reachable)
        self.assertIn(repo.current_commit(), reachable)
        self.assertIn(repo.commits[0], reachable)

    def test_update_writes_generated_html_as_utf8(self):
        repo = Repo()
        visualizer = GraphVisualizer()
        network = Mock()
        network.generate_html.return_value = "<html>\\u2234</html>"

        with patch.object(GraphVisualizer, "_network", return_value=network):
            visualizer.update(repo)

        source = visualizer.path.read_text(encoding="utf-8")
        self.assertIn("<html>\\u2234</html>", source)
        network.write_html.assert_not_called()

    def test_graph_page_polls_json_without_refreshing_page(self):
        repo = Repo()
        visualizer = GraphVisualizer()
        network = Mock()
        network.generate_html.return_value = "<html></html>"

        with patch.object(GraphVisualizer, "_network", return_value=network):
            visualizer.update(repo)

        source = visualizer.path.read_text(encoding="utf-8")
        self.assertIn('fetch("/graph-data"', source)
        self.assertIn("syncDataSet(nodes", source)
        self.assertNotIn('http-equiv="refresh"', source)

    def test_graph_data_updates_existing_nodes_and_adds_new_ones(self):
        repo = Repo()
        first = _graph_data(repo, 1)

        commit(repo, 9)
        second = _graph_data(repo, 2)
        second_commit_nodes = [node for node in second["nodes"] if node["id"].isdigit()]

        self.assertEqual(first["version"], 1)
        self.assertEqual(second["version"], 2)
        self.assertEqual([node["id"] for node in second_commit_nodes], ["0", "1"])
        self.assertIn({"from": "1", "to": "0"}, [{"from": edge["from"], "to": edge["to"]} for edge in second["edges"]])

    def test_graph_data_omits_commits_unreachable_from_any_branch_or_tag(self):
        repo = Repo()
        commit(repo, 1)
        commit(repo, 2)
        reset(repo, ConstantOffsetRef(HeadRef(), 1))

        data = _graph_data(repo, 1)
        commit_node_ids = {node["id"] for node in data["nodes"] if node["id"].isdigit()}

        self.assertEqual(commit_node_ids, {"0", "1"})

    def test_graph_data_shows_refs_as_separate_nodes(self):
        repo = Repo()
        commit(repo, 7)
        repo.create_tag("saved", repo.current_commit())

        data = _graph_data(repo, 1)
        commit_labels = [
            node["label"]
            for node in data["nodes"]
            if node["id"].isdigit()
        ]
        ref_nodes = {
            node["id"]: node
            for node in data["nodes"]
            if not node["id"].isdigit()
        }

        self.assertNotIn("branch:main", "\n".join(commit_labels))
        self.assertIn("global:branch:main", ref_nodes)
        self.assertIn("global:tag:saved", ref_nodes)
        self.assertIn("HEAD", ref_nodes)
        self.assertEqual(ref_nodes["global:branch:main"]["shape"], "box")
        self.assertEqual(ref_nodes["global:tag:saved"]["shape"], "ellipse")

    def test_graph_data_ghosts_outer_frame_refs_and_commits(self):
        repo = Repo()
        commit(repo, 1)
        branch(repo, "side")
        checkout(repo, "side")
        commit(repo, 2)
        checkout(repo, "main")
        repo.push_function_frame({}, {})

        data = _graph_data(repo, 1)
        nodes = {node["id"]: node for node in data["nodes"]}
        edges = {edge["id"]: edge for edge in data["edges"]}

        self.assertIn("rgba", nodes["2"]["color"]["background"])
        self.assertIn("rgba", nodes["global:branch:side"]["color"]["background"])
        self.assertIn("rgba", edges["2->1"]["color"])
        self.assertNotIn("rgba", nodes["frame 1:HEAD"]["color"]["background"])

    def test_graph_data_shows_previous_stack_frame_heads_translucently(self):
        repo = Repo()
        commit(repo, 1)
        repo.push_function_frame({}, {})

        data = _graph_data(repo, 1)
        nodes = {node["id"]: node for node in data["nodes"]}
        edges = {edge["id"]: edge for edge in data["edges"]}

        self.assertEqual(nodes["global:HEAD"]["label"], "HEAD")
        self.assertIn("rgba", nodes["global:HEAD"]["color"]["background"])
        self.assertIn("global:HEAD->global:branch:main", edges)

    def test_graph_data_numbers_current_and_saved_function_heads_by_frame(self):
        repo = Repo()
        repo.push_function_frame({}, {})
        repo.push_function_frame({}, {})

        data = _graph_data(repo, 1)
        nodes = {node["id"]: node for node in data["nodes"]}
        edges = {edge["id"]: edge for edge in data["edges"]}

        self.assertEqual(nodes["frame 1:saved-head"]["label"], "HEAD 1")
        self.assertEqual(nodes["frame 2:HEAD"]["label"], "HEAD 2")
        self.assertIn("frame 1:saved-head->frame 1:branch:main", edges)
        self.assertIn("frame 2:HEAD->frame 2:branch:main", edges)

    def test_head_points_to_checked_out_branch_node(self):
        repo = Repo()
        repo.push_function_frame({}, {})

        data = _graph_data(repo, 1)
        edges = {edge["id"]: edge for edge in data["edges"]}

        self.assertIn("frame 1:HEAD->frame 1:branch:main", edges)
        self.assertNotIn("frame 1:HEAD->0", edges)

    def test_ref_nodes_continue_outward_from_the_commit(self):
        repo = Repo()
        repo.push_function_frame({}, {})

        data = _graph_data(repo, 1)
        nodes = {node["id"]: node for node in data["nodes"]}
        commit_x = nodes["0"]["x"]
        branch_x = nodes["frame 1:branch:main"]["x"]
        head_x = nodes["frame 1:HEAD"]["x"]

        self.assertLess(branch_x, commit_x)
        self.assertLess(head_x, branch_x)

    def test_bound_branch_points_to_caller_branch_node_and_target_is_opaque(self):
        repo = Repo()
        commit(repo, 1)
        branch(repo, "side")
        binding = repo.bind_caller_branch("side")
        repo.push_function_frame({"target": binding}, {"target": "side"})

        data = _graph_data(repo, 1)
        nodes = {node["id"]: node for node in data["nodes"]}
        edges = {edge["id"]: edge for edge in data["edges"]}

        self.assertIn("frame 1:branch:target->global:branch:side", edges)
        self.assertNotIn("rgba", nodes["global:branch:side"]["color"]["background"])

    def test_pyvis_node_renames_id_for_python_api_only(self):
        node = {"id": "7", "label": "commit"}

        self.assertEqual(_pyvis_node(node), {"n_id": "7", "label": "commit"})
        self.assertEqual(node, {"id": "7", "label": "commit"})

    def test_pyvis_edge_renames_from_for_python_api_only(self):
        edge = {"id": "7->6", "from": "7", "to": "6"}

        self.assertEqual(_pyvis_edge(edge), {"id": "7->6", "source": "7", "to": "6"})
        self.assertEqual(edge, {"id": "7->6", "from": "7", "to": "6"})

    def test_updates_after_initial_page_write_only_change_json_data(self):
        repo = Repo()
        visualizer = GraphVisualizer()
        network = Mock()
        network.generate_html.return_value = "<html></html>"

        with patch.object(GraphVisualizer, "_network", return_value=network):
            visualizer.update(repo)
            commit(repo, 5)
            visualizer.update(repo)

        network.generate_html.assert_called_once()
        self.assertEqual(visualizer._data["version"], 2)
        commit_node_ids = {node["id"] for node in visualizer._data["nodes"] if node["id"].isdigit()}
        self.assertEqual(commit_node_ids, {"0", "1"})


if __name__ == "__main__":
    unittest.main()
