import html
import json
import tempfile
import threading
import webbrowser
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gitscript.commit import Commit
from gitscript.commit_range import reachable_commits
from gitscript.repo import BranchBinding, CallerBinding, CommitBinding, NameBinding, ProtectedBinding, Repo, TagBinding


@dataclass
class RefNode:
    id: str
    label: str
    kind: str
    commit: Commit
    protected: bool = False
    active: bool = True
    root_active: bool = True
    target_id: str | None = None


class GraphVisualizer:
    def __init__(self, poll_seconds: float = 0.15):
        self.poll_seconds = poll_seconds
        self.directory = Path(tempfile.mkdtemp(prefix="gitscript_graph_"))
        self.path = self.directory / "graph.html"
        self._data: dict[str, object] = {"version": 0, "nodes": [], "edges": []}
        self._version = 0
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._opened = False

    def start(self, repo: Repo) -> None:
        self._ensure_pyvis()
        self.update(repo)
        url = self._start_server()
        webbrowser.open(url, new=1)
        self._opened = True

    def update(self, repo: Repo) -> None:
        self._version += 1
        self._data = _graph_data(repo, self._version)
        if not self.path.exists():
            self._write_graph_page()

    def _write_graph_page(self) -> None:
        network = self._network()
        for node in self._data["nodes"]:
            network.add_node(**_pyvis_node(node))
        for edge in self._data["edges"]:
            network.add_edge(**_pyvis_edge(edge))

        self.path.write_text(network.generate_html(notebook=False), encoding="utf-8")
        _inject_live_update_script(self.path, self.poll_seconds)

    @staticmethod
    def _ensure_pyvis() -> None:
        try:
            import pyvis  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("Visualization requires PyVis. Install dependencies with `pip install -e .`.") from exc

    @staticmethod
    def _network():
        from pyvis.network import Network

        network = Network(
            height="100vh",
            width="100%",
            directed=True,
            bgcolor="#f8fafc",
            font_color="#111827",
            cdn_resources="in_line",
        )
        network.set_options("""
        {
          "physics": {"enabled": true},
          "layout": {"improvedLayout": false},
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true,
            "multiselect": true
          },
          "edges": {
            "smooth": {"enabled": true, "type": "cubicBezier", "forceDirection": "vertical", "roundness": 0.45}
          }
        }
        """)
        return network

    def _start_server(self) -> str:
        if self._server is not None:
            return self._server_url()

        visualizer = self

        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                if self.path == "/graph-data":
                    body = json.dumps(visualizer._data).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                super().do_GET()

        handler = partial(Handler, directory=str(self.directory))
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        return self._server_url()

    def _server_url(self) -> str:
        if self._server is None:
            raise RuntimeError("Visualizer server has not started")
        host, port = self._server.server_address
        return f"http://{host}:{port}/graph.html"


def _graph_data(repo: Repo, version: int) -> dict[str, object]:
    nodes = []
    edges = []
    refs = _all_ref_nodes(repo)
    reachable = _reachable_commits_from_refs(refs)
    active_reachable = _reachable_commits_from_refs([ref for ref in refs if ref.root_active])
    commits = [commit for commit in repo.commits if commit in reachable]
    positions = _commit_positions(commits)

    refs_by_commit: dict[Commit, list[RefNode]] = {}
    for ref in refs:
        if ref.commit in reachable:
            refs_by_commit.setdefault(ref.commit, []).append(ref)
    ref_positions = _ref_positions(refs, positions)

    for commit in sorted(commits, key=lambda c: c.order):
        x, y = positions[commit]
        active = commit in active_reachable
        nodes.append({
            "id": str(commit.order),
            "label": _node_label(commit),
            "title": _node_title(commit),
            "x": x,
            "y": y,
            "fixed": {"x": True, "y": True},
            "shape": "box",
            "color": _commit_node_color(commit, active),
            "font": {"face": "Consolas", "size": 16, "color": _font_color(active)},
            "borderWidth": 1,
        })

        for ref in refs_by_commit.get(commit, []):
            ref_x, ref_y = ref_positions[ref.id]
            nodes.append(_ref_node_data(ref, ref_x, ref_y))
            target = ref.target_id if ref.target_id is not None else str(commit.order)
            edges.append({
                "id": f"{ref.id}->{target}",
                "from": ref.id,
                "to": target,
                "arrows": "to",
                "color": _ref_edge_color(ref),
                "width": 1 if ref.active else 0.5,
                "dashes": ref.kind == "tag",
            })

    commit_set = set(commits)
    for commit in sorted(commits, key=lambda c: c.order):
        if commit.parent is None or commit.parent not in commit_set:
            continue
        edges.append({
            "id": f"{commit.order}->{commit.parent.order}",
            "from": str(commit.order),
            "to": str(commit.parent.order),
            "arrows": "to",
            "color": "#475569" if commit in active_reachable and commit.parent in active_reachable else "rgba(100, 116, 139, 0.24)",
            "width": 2 if commit in active_reachable and commit.parent in active_reachable else 1,
        })

    return {"version": version, "nodes": nodes, "edges": edges}


def _pyvis_node(node: dict[str, object]) -> dict[str, object]:
    node = dict(node)
    node["n_id"] = node.pop("id")
    return node


def _pyvis_edge(edge: dict[str, object]) -> dict[str, object]:
    edge = dict(edge)
    edge["source"] = edge.pop("from")
    return edge


def _visible_reachable_commits(repo: Repo) -> set[Commit]:
    return _reachable_commits_from_refs(_all_ref_nodes(repo))


def _reachable_commits_from_refs(refs: list[RefNode]) -> set[Commit]:
    commits: set[Commit] = set()
    for ref in refs:
        commits.update(reachable_commits(ref.commit))
    return commits


def _all_ref_nodes(repo: Repo) -> list[RefNode]:
    refs: list[RefNode] = []
    current_frame = repo.current_frame()
    global_active = current_frame is None
    frame_depths = {id(frame): depth for depth, frame in enumerate(repo.call_stack, start=1)}
    branch_dict_ids: dict[int, str] = {id(repo.branches): "global"}
    tag_dict_ids: dict[int, str] = {id(repo.tags): "global"}
    for depth, frame in enumerate(repo.call_stack, start=1):
        branch_dict_ids[id(frame.branches)] = f"frame {depth}"
        tag_dict_ids[id(frame.tags)] = f"frame {depth}"

    for name, commit in repo.branches.items():
        refs.append(RefNode(
            f"global:branch:{name}",
            _ref_label(name, "branch", "global", name == "main"),
            "branch",
            commit,
            name == "main",
            global_active,
            global_active,
        ))
    for name, commit in repo.tags.items():
        refs.append(RefNode(
            f"global:tag:{name}",
            _ref_label(name, "tag", "global"),
            "tag",
            commit,
            active=global_active,
            root_active=global_active,
        ))

    for depth, frame in enumerate(repo.call_stack, start=1):
        frame_name = f"frame {depth}"
        frame_active = frame is current_frame
        if "main" in frame.bindings:
            caller_depth = depth - 1
            target_id = _head_target_id_for_depth(repo, caller_depth, frame.caller_head)
            head_id = "global:HEAD" if caller_depth == 0 else f"frame {caller_depth}:saved-head"
            head_label = "HEAD" if caller_depth == 0 else f"HEAD {caller_depth}"
            refs.append(RefNode(
                head_id,
                head_label,
                "head",
                frame.bindings["main"].resolve(),
                True,
                False,
                False,
                target_id,
            ))
        for name, binding in frame.bindings.items():
            if isinstance(binding, CommitBinding):
                continue
            if binding.is_branch():
                visible = repo.visible_name(name) if frame_active else name
                protected = binding.is_protected()
                refs.append(RefNode(
                    f"{frame_name}:branch:{name}",
                    _ref_label(visible, "branch", frame_name, protected),
                    "branch",
                    binding.resolve(),
                    protected,
                    frame_active,
                    frame_active,
                    _binding_target_id(binding, branch_dict_ids, tag_dict_ids),
                ))
            elif binding.is_tag():
                visible = repo.visible_name(name) if frame_active else name
                refs.append(RefNode(
                    f"{frame_name}:tag:{name}",
                    _ref_label(visible, "tag", frame_name),
                    "tag",
                    binding.resolve(),
                    active=frame_active,
                    root_active=frame_active,
                    target_id=_binding_target_id(binding, branch_dict_ids, tag_dict_ids),
                ))

        for name, commit in frame.branches.items():
            refs.append(RefNode(
                f"{frame_name}:branch-local:{name}",
                _ref_label(name, "branch", frame_name),
                "branch",
                commit,
                active=frame_active,
                root_active=frame_active,
            ))
        for name, commit in frame.tags.items():
            refs.append(RefNode(
                f"{frame_name}:tag-local:{name}",
                _ref_label(name, "tag", frame_name),
                "tag",
                commit,
                active=frame_active,
                root_active=frame_active,
            ))

    try:
        current_head_id = "HEAD"
        current_head_label = "HEAD"
        if current_frame is not None:
            current_depth = frame_depths[id(current_frame)]
            current_head_id = f"frame {current_depth}:HEAD"
            current_head_label = f"HEAD {current_depth}"
        refs.append(RefNode(
            current_head_id,
            current_head_label,
            "head",
            repo.current_commit(),
            True,
            True,
            False,
            _head_target_id(repo, frame_depths),
        ))
    except RuntimeError:
        pass

    active_targets = {ref.target_id for ref in refs if ref.active and ref.target_id is not None}
    for ref in refs:
        if ref.id in active_targets:
            ref.active = True
    return refs


def _head_target_id_for_depth(repo: Repo, depth: int, head: str) -> str:
    if depth == 0:
        return f"global:branch:{head}"
    frame = repo.call_stack[depth - 1]
    if head in frame.bindings:
        return f"frame {depth}:branch:{head}"
    return f"frame {depth}:branch-local:{head}"


def _head_target_id(repo: Repo, frame_depths: dict[int, int]) -> str | None:
    frame = repo.current_frame()
    if frame is None:
        return f"global:branch:{repo.HEAD}"
    depth = frame_depths[id(frame)]
    if repo.HEAD in frame.bindings:
        return f"frame {depth}:branch:{repo.HEAD}"
    return f"frame {depth}:branch-local:{repo.HEAD}"


def _binding_target_id(
        binding,
        branch_dict_ids: dict[int, str],
        tag_dict_ids: dict[int, str],
) -> str | None:
    if isinstance(binding, ProtectedBinding):
        return _binding_target_id(binding.binding, branch_dict_ids, tag_dict_ids)
    if isinstance(binding, CallerBinding):
        return _binding_target_id(binding.binding, branch_dict_ids, tag_dict_ids)
    if isinstance(binding, BranchBinding):
        frame = branch_dict_ids.get(id(binding.branches))
        if frame is None:
            return None
        if frame == "global":
            return f"global:branch:{binding.name}"
        return f"{frame}:branch-local:{binding.name}"
    if isinstance(binding, TagBinding):
        frame = tag_dict_ids.get(id(binding.tags))
        if frame is None:
            return None
        if frame == "global":
            return f"global:tag:{binding.name}"
        return f"{frame}:tag-local:{binding.name}"
    if isinstance(binding, NameBinding):
        if binding.name in binding.branches:
            frame = branch_dict_ids.get(id(binding.branches))
            if frame == "global":
                return f"global:branch:{binding.name}"
            if frame is not None:
                return f"{frame}:branch-local:{binding.name}"
        if binding.name in binding.tags:
            frame = tag_dict_ids.get(id(binding.tags))
            if frame == "global":
                return f"global:tag:{binding.name}"
            if frame is not None:
                return f"{frame}:tag-local:{binding.name}"
    return None


def _visible_ref_roots(repo: Repo) -> list[Commit]:
    roots = []
    for ref in _all_ref_nodes(repo):
        if ref.kind in {"branch", "tag"}:
            roots.append(ref.commit)
    return roots


def _ref_label(name: str, kind: str, frame: str, protected: bool = False) -> str:
    suffix = " !" if protected else ""
    if frame == "global":
        return f"{kind}:{name}{suffix}"
    return f"{frame}\n{kind}:{name}{suffix}"


def _ref_position(commit_x: int, commit_y: int, index: int) -> tuple[int, int]:
    side = -1 if index % 2 == 0 else 1
    row = index // 2
    return commit_x + side * 210, commit_y + row * 44 - 34


def _ref_positions(refs: list[RefNode], commit_positions: dict[Commit, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    refs_by_id = {ref.id: ref for ref in refs}
    direct_indexes: dict[Commit, int] = {}
    dependent_indexes: dict[str, int] = {}
    positions: dict[str, tuple[int, int]] = {}

    def place(ref: RefNode) -> tuple[int, int]:
        if ref.id in positions:
            return positions[ref.id]

        commit_x, commit_y = commit_positions[ref.commit]
        if ref.target_id is None or ref.target_id not in refs_by_id:
            index = direct_indexes.get(ref.commit, 0)
            direct_indexes[ref.commit] = index + 1
            positions[ref.id] = _ref_position(commit_x, commit_y, index)
            return positions[ref.id]

        target_x, target_y = place(refs_by_id[ref.target_id])
        direction = 1 if target_x >= commit_x else -1
        index = dependent_indexes.get(ref.target_id, 0)
        dependent_indexes[ref.target_id] = index + 1
        positions[ref.id] = (target_x + direction * 170, target_y + index * 34)
        return positions[ref.id]

    for ref in refs:
        place(ref)

    return positions


def _ref_node_data(ref: RefNode, x: int, y: int) -> dict[str, object]:
    return {
        "id": ref.id,
        "label": ref.label,
        "title": html.escape(f"{ref.kind} -> commit #{ref.commit.order}"),
        "x": x,
        "y": y,
        "fixed": {"x": True, "y": True},
        "shape": "box" if ref.kind == "branch" else "ellipse",
        "color": _ref_node_color(ref),
        "font": {"face": "Consolas", "size": 13, "color": _font_color(ref.active)},
        "borderWidth": 3 if ref.protected else 1,
        "margin": 8,
    }


def _ref_node_color(ref: RefNode) -> dict[str, object]:
    if not ref.active:
        if ref.kind == "head":
            return {
                "background": "rgba(134, 239, 172, 0.24)",
                "border": "rgba(22, 163, 74, 0.38)",
                "highlight": {"background": "rgba(187, 247, 208, 0.34)", "border": "rgba(21, 128, 61, 0.5)"},
            }
        if ref.kind == "tag":
            return {
                "background": "rgba(196, 181, 253, 0.24)",
                "border": "rgba(124, 58, 237, 0.38)",
                "highlight": {"background": "rgba(221, 214, 254, 0.34)", "border": "rgba(109, 40, 217, 0.5)"},
            }
        return {
            "background": "rgba(147, 197, 253, 0.24)",
            "border": "rgba(37, 99, 235, 0.38)",
            "highlight": {"background": "rgba(191, 219, 254, 0.34)", "border": "rgba(29, 78, 216, 0.5)"},
        }
    if ref.kind == "head":
        return {
            "background": "#dcfce7",
            "border": "#16a34a",
            "highlight": {"background": "#bbf7d0", "border": "#15803d"},
        }
    if ref.kind == "tag":
        return {
            "background": "#ede9fe",
            "border": "#7c3aed",
            "highlight": {"background": "#ddd6fe", "border": "#6d28d9"},
        }
    return {
        "background": "#dbeafe",
        "border": "#2563eb",
        "highlight": {"background": "#bfdbfe", "border": "#1d4ed8"},
    }


def _ref_edge_color(ref: RefNode) -> str:
    if not ref.active:
        return "rgba(100, 116, 139, 0.24)"
    if ref.kind == "head":
        return "#16a34a"
    if ref.kind == "tag":
        return "#7c3aed"
    return "#2563eb"


def _font_color(active: bool) -> str:
    return "#111827" if active else "rgba(17, 24, 39, 0.42)"


def _commit_positions(commits: list[Commit]) -> dict[Commit, tuple[int, int]]:
    if not commits:
        return {}

    sorted_commits = sorted(commits, key=lambda c: c.order)
    max_index = len(sorted_commits) - 1
    next_column = 0
    columns: dict[Commit, int] = {}
    child_counts: dict[Commit, int] = {}

    for commit in sorted_commits:
        parent = commit.parent
        if parent is None or parent not in columns:
            columns[commit] = next_column
            next_column += 1
            continue

        child_index = child_counts.get(parent, 0)
        child_counts[parent] = child_index + 1
        if child_index == 0:
            columns[commit] = columns[parent]
        else:
            columns[commit] = next_column
            next_column += 1

    center = (next_column - 1) / 2
    return {
        commit: (int((columns[commit] - center) * 240), int((max_index - index) * 130))
        for index, commit in enumerate(sorted_commits)
    }


def _node_label(commit: Commit) -> str:
    return f"#{commit.order}\nvalue={commit.value}\nchar={_char_text(commit.value)}"


def _node_title(commit: Commit) -> str:
    parent = "none" if commit.parent is None else f"#{commit.parent.order}"
    return html.escape(
        f"commit #{commit.order}\n"
        f"value: {commit.value}\n"
        f"char: {_char_text(commit.value)}\n"
        f"parent: {parent}"
    )


def _char_text(value: int) -> str:
    try:
        return repr(chr(value))
    except (ValueError, OverflowError):
        return "N/A"


def _commit_node_color(commit: Commit, active: bool = True) -> dict[str, object]:
    if not active:
        return {
            "background": "rgba(148, 163, 184, 0.22)",
            "border": "rgba(100, 116, 139, 0.42)",
            "highlight": {"background": "rgba(148, 163, 184, 0.35)", "border": "#64748b"},
        }
    if commit.parent is None:
        return {
            "background": "#ecfeff",
            "border": "#0891b2",
            "highlight": {"background": "#cffafe", "border": "#0e7490"},
        }
    return {
        "background": "#fef3c7",
        "border": "#d97706",
        "highlight": {"background": "#fde68a", "border": "#b45309"},
    }


def _inject_live_update_script(path: Path, poll_seconds: float) -> None:
    source = path.read_text(encoding="utf-8")
    poll_ms = int(poll_seconds * 1000)
    live_update = f"""
<style>body {{ margin: 0; }} .card {{ border-radius: 8px; }}</style>
<script>
const pollMs = {poll_ms};
let knownVersion = null;

function syncDataSet(dataSet, nextItems) {{
  const nextIds = new Set(nextItems.map((item) => item.id));
  const staleIds = dataSet.getIds().filter((id) => !nextIds.has(id));
  if (staleIds.length) {{
    dataSet.remove(staleIds);
  }}
  dataSet.update(nextItems);
}}

async function refreshGraphData() {{
  const response = await fetch("/graph-data", {{cache: "no-store"}});
  const state = await response.json();
  if (knownVersion === state.version) {{
    return;
  }}
  knownVersion = state.version;
  syncDataSet(nodes, state.nodes);
  syncDataSet(edges, state.edges);
}}

setInterval(() => refreshGraphData().catch(() => {{}}), pollMs);
refreshGraphData().catch(() => {{}});
</script>"""
    if "<head>" in source:
        source = source.replace("<head>", f"<head>\n{live_update}", 1)
    else:
        source = live_update + source
    path.write_text(source, encoding="utf-8")
