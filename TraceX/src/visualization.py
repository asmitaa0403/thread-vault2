from __future__ import annotations

import json
import math

import networkx as nx

from .analysis import analyze_case_graph
from .graph import build_case_graph


def _node_color(entity_type: str) -> str:
    return {
        "PERSON": "#1f77b4",
        "ORGANIZATION": "#2ca02c",
        "LOCATION": "#ff7f0e",
    }.get(entity_type.upper(), "#7f7f7f")


def create_network_html(case_id: str, height: int = 900) -> str:
    """Create deterministic, manually positioned vis-network HTML."""
    graph = build_case_graph(case_id)
    ranking = analyze_case_graph(graph)
    influence_map = {row["canonical_id"]: row["influence_score"] for row in ranking}
    top_id = ranking[0]["canonical_id"] if ranking else None

    positions = {}
    distances = {}
    if top_id and top_id in graph:
        distances = nx.single_source_shortest_path_length(graph, top_id)
        positions[top_id] = (0.0, 0.0)
        direct = sorted((node for node, distance in distances.items() if distance == 1), key=str)
        first_radius = max(3.0, 0.82 * len(direct))
        direct_angles = {}
        for index, node in enumerate(direct):
            angle = 2 * math.pi * index / max(1, len(direct)) - math.pi / 2
            direct_angles[node] = angle
            positions[node] = (math.cos(angle) * first_radius, math.sin(angle) * first_radius)

        for distance in (2, 3):
            members = sorted((node for node, value in distances.items() if value == distance), key=str)
            for index, node in enumerate(members):
                parents = sorted((parent for parent in graph.neighbors(node) if parent in positions), key=str)
                parent = parents[0] if parents else top_id
                parent_x, parent_y = positions[parent]
                parent_angle = direct_angles.get(parent, math.atan2(parent_y, parent_x))
                siblings = sorted((candidate for candidate in graph.neighbors(parent) if candidate in members), key=str)
                sibling_index = siblings.index(node) if node in siblings else index
                sibling_count = max(1, len(siblings))
                sector = min(1.25, 0.9 + 0.18 * sibling_count)
                angle = parent_angle + (sibling_index - (sibling_count - 1) / 2) * (sector / sibling_count)
                radius = 2.15 if distance == 2 else 1.8
                positions[node] = (parent_x + math.cos(angle) * radius, parent_y + math.sin(angle) * radius)

        disconnected = [set(component) for component in nx.connected_components(graph) if top_id not in component]
        for component_index, component in enumerate(disconnected):
            angle = 2 * math.pi * component_index / max(1, len(disconnected))
            anchor_radius = first_radius + 3.0
            anchor = (math.cos(angle) * anchor_radius, math.sin(angle) * anchor_radius)
            members = sorted(component, key=str)
            for member_index, node in enumerate(members):
                member_angle = 2 * math.pi * member_index / max(1, len(members))
                positions[node] = (anchor[0] + math.cos(member_angle), anchor[1] + math.sin(member_angle))
    else:
        positions = nx.spring_layout(graph, seed=42)

    width = 1200
    canvas_height = 760
    center_x = width / 2
    center_y = canvas_height / 2
    xs = [point[0] for point in positions.values()] or [0.0]
    ys = [point[1] for point in positions.values()] or [0.0]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    scale = min(width / (span * 1.25), canvas_height / (span * 1.25))

    nodes = []
    for node_id, data in graph.nodes(data=True):
        score = float(influence_map.get(node_id, 0.0))
        distance = distances.get(node_id)
        if node_id == top_id:
            size = 44
        elif distance == 1:
            size = max(28, min(38, 25 + int(score * 70)))
        elif distance is not None:
            size = max(22, min(32, 20 + int(score * 55)))
        else:
            size = max(16, min(24, 16 + int(score * 35)))

        label = str(data.get("canonical_name") or node_id)
        if len(label) > 18:
            words = label.split()
            midpoint = max(1, len(words) // 2)
            label = "\n".join((" ".join(words[:midpoint]), " ".join(words[midpoint:])))
        px, py = positions.get(node_id, (0.0, 0.0))
        node = {
            "id": node_id,
            "label": label,
            "group": data.get("entity_type") or "UNKNOWN",
            "title": str(data.get("canonical_name") or node_id),
            "color": _node_color(data.get("entity_type", "UNKNOWN")),
            "size": size,
            "value": size,
            "x": int(center_x + px * scale),
            "y": int(center_y + py * scale),
            "physics": False,
        }
        if node_id == top_id:
            node["color"] = {
                "background": "#c0392b",
                "border": "#ff8a80",
                "highlight": {"background": "#e74c3c", "border": "#ffd1cc"},
            }
            node["borderWidth"] = 5
        nodes.append(node)

    edges = []
    for index, (source, target, data) in enumerate(graph.edges(data=True)):
        raw_type = (data.get("relationship_type") or "ASSOCIATED_WITH").upper()
        relationship = {"CALLED": "CALL", "TAGGED_WITH": "ASSOCIATED_WITH"}.get(raw_type, raw_type)
        edge = {
            "from": source,
            "to": target,
            "label": relationship,
            "title": relationship,
            "arrows": "to",
            "smooth": {"enabled": True, "type": "curvedCW" if index % 2 == 0 else "curvedCCW", "roundness": 0.14 + (index % 3) * 0.06},
            "font": {"background": "#0e1117", "strokeWidth": 3, "strokeColor": "#0e1117", "align": "horizontal"},
        }
        if relationship == "PAID":
            edge["color"] = {"color": "#e0a458", "highlight": "#f2c078"}
            edge["width"] = 2.5
        elif relationship == "CALL":
            edge["color"] = {"color": "#7fa8c9", "highlight": "#a9c9e2"}
        edges.append(edge)

    html_page = """
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<link href="https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.css" rel="stylesheet" type="text/css" />
<style>
body { margin:0; padding:0; background:#0e1117; color:#e6eef3; }
#mynetwork { width:100%; height:__HEIGHT__px; border:1px solid rgba(255,255,255,.06); position:relative; }
.legend { color:#cbd5e1; font-family:Arial,sans-serif; font-size:13px; }
</style>
</head>
<body>
<div style="padding:12px 16px; color:#cbd5e1; font-family:Arial,Helvetica,sans-serif; font-size:14px">
<strong>How to read this network</strong>
<div style="margin-top:8px; display:flex; gap:12px; align-items:center; flex-wrap:wrap">
<div class="legend">PERSON</div><div class="legend">ORGANIZATION</div><div class="legend">LOCATION</div>
</div>
<div style="margin-top:8px; font-size:13px">CALL = communication · PAID = financial transfer · SEEN_AT = location association · ASSOCIATED_WITH = general association</div>
</div>
<div id="mynetwork"><div id="mynetwork-fallback" style="padding:18px;color:#cbd5e1">Loading network...</div></div>
<script>
function loadScript(url){return new Promise(function(resolve,reject){var script=document.createElement('script');script.src=url;script.async=true;script.onload=resolve;script.onerror=reject;document.head.appendChild(script);});}
function initNetwork(){try{
const nodes=new vis.DataSet(__NODES__); const edges=new vis.DataSet(__EDGES__); const container=document.getElementById('mynetwork');
var fallback=document.getElementById('mynetwork-fallback'); if(fallback){fallback.style.display='none';}
const network=new vis.Network(container,{nodes:nodes,edges:edges},{
physics:{enabled:false},
nodes:{shape:'dot',size:22,font:{color:'#ffffff',size:15,face:'Arial',strokeWidth:4,strokeColor:'#0e1117',align:'center',multi:'html'},borderWidth:2,scaling:{min:16,max:56}},
edges:{color:{color:'#9aa4ae'},arrows:{to:{enabled:true,scaleFactor:.7}},font:{align:'horizontal',size:11,color:'#e6eef3',background:'#0e1117',strokeWidth:3,strokeColor:'#0e1117'},smooth:{enabled:true,type:'continuous',roundness:.2}},
interaction:{hover:true,multiselect:false,dragNodes:true,zoomView:true},layout:{improvedLayout:false},autoResize:true,width:'100%',height:'100%'
});
network.fit({padding:72,animation:false});
network.on('selectNode',function(params){var nodeId=params.nodes&&params.nodes.length?params.nodes[0]:null;if(nodeId){window.parent.postMessage({type:'threadvault_select',node:nodeId},'*');}});
}catch(error){console.error('vis init failed',error);var fallback=document.getElementById('mynetwork-fallback');if(fallback){fallback.style.display='block';fallback.innerText='Network visualization failed to load.';}}}
(function(){if(typeof vis!=='undefined'){initNetwork();}else{loadScript('https://unpkg.com/vis-network@9.1.2/dist/vis-network.min.js').then(initNetwork).catch(function(){var fallback=document.getElementById('mynetwork-fallback');if(fallback){fallback.innerText='Network visualization failed to load.';}});}})();
</script>
</body>
</html>
"""
    return (html_page.replace("__NODES__", json.dumps(nodes)).replace("__EDGES__", json.dumps(edges)).replace("__HEIGHT__", str(height)))
