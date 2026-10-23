import streamlit as st
import streamlit.components.v1 as components

from src.ingestion import get_available_cases, load_case
from src.entity_resolution import process_case
from src.graph import build_case_graph
from src.analysis import analyze_case_graph
from src.anomaly import detect_patterns
from src.explainability import explain_patterns, get_investigation_timeline
from src.visualization import create_network_html
from src.audit import append_audit_event, get_audit_log, verify_audit_chain
import pandas as pd
from typing import Dict


def _local_style():
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0e1117;
            color: #e6eef3;
        }
        .main .block-container{
            padding-top: 1rem;
            padding-bottom: 2rem;
        }
        .stButton>button {
            background-color: #2b6cb0;
            color: white;
        }
        .metric-label {
            color: #cbd5e1;
        }
        .brief-card, .lead-card, .timeline-card, .entity-card {
            background: #111923;
            border: 1px solid #263445;
            border-radius: 8px;
            padding: 1rem 1.1rem;
            margin: .35rem 0 1rem 0;
        }
        .brief-kicker, .eyebrow {
            color: #8fa6bd;
            font-size: .72rem;
            font-weight: 700;
            letter-spacing: .08em;
            text-transform: uppercase;
        }
        .brief-title {
            color: #f5f7fa;
            font-size: 1.35rem;
            font-weight: 700;
            margin: .25rem 0 .15rem 0;
        }
        .muted { color: #9fb0c0; }
        .lead-card.high { border-left: 5px solid #d53e4f; }
        .lead-card.medium { border-left: 5px solid #f0ad4e; }
        .lead-card.low { border-left: 5px solid #2ca02c; }
        .lead-title { color: #f5f7fa; font-size: 1.05rem; font-weight: 700; }
        .lead-severity { font-size: .75rem; font-weight: 800; letter-spacing: .08em; }
        .timeline-card { border-left: 3px solid #4d7698; }
        .timeline-date { color: #8fa6bd; font-size: .78rem; font-weight: 700; }
        .timeline-type { color: #f5f7fa; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_case_details(case_id: str):
    case_data = load_case(case_id)
    counts = case_data["counts"]

    st.subheader(f"Case: {case_id}")
    st.caption("Dataset record counts from the synthetic investigation files")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(label="FIR records", value=str(counts.get("fir", 0)))
    col2.metric(label="CDR records", value=str(counts.get("cdr", 0)))
    col3.metric(label="Transactions", value=str(counts.get("transactions", 0)))
    col4.metric(label="Social-media records", value=str(counts.get("social", 0)))

    # Analytical results are shown in Phase 2 (Entity Intelligence) and Phase 3 (Network Analysis)


def _render_entity_intelligence(case_id: str):
    # cache/process the case to extract and resolve entities
    res = process_case(case_id)
    counts = res["counts"]

    st.markdown("## Entity Intelligence")
    st.write("Automatic entity extraction + conservative canonical resolution (Phase 2).")

    col1, col2 = st.columns(2)
    col1.metric("Total Extracted Entities", str(counts.get("total_extracted", 0)))
    col2.metric("Total Canonical Entities", str(counts.get("total_canonical", 0)))

    # per-type counts
    by_type = counts.get("by_type", {})
    types = ["PERSON", "PHONE", "VEHICLE", "LOCATION", "ORGANIZATION", "ACCOUNT"]
    cols = st.columns(len(types))
    for i, t in enumerate(types):
        cols[i].metric(t, str(by_type.get(t, 0)))

    # Build canonical table
    canonical = res["canonical_entities"]
    rows: list[Dict] = []
    for cid, ce in canonical.items():
        rows.append(
            {
                "canonical_id": cid,
                "entity_type": ce.entity_type,
                "canonical_name": ce.canonical_name,
                "aliases": ", ".join(sorted(set(ce.aliases))) if ce.aliases else "",
                "source_count": len(ce.source_records),
            }
        )

    df = pd.DataFrame(rows)

    st.markdown("### Canonical Entities")
    q = st.text_input("Search canonical name or alias")
    if q:
        ql = q.lower()
        df = df[df.apply(lambda r: ql in str(r["canonical_name"]).lower() or ql in str(r["aliases"]).lower(), axis=1)]

    st.dataframe(df.reset_index(drop=True))

    selected = st.selectbox("Select entity to view details", options=["-- none --"] + df["canonical_id"].tolist())
    if selected and selected != "-- none --":
        ce = canonical[selected]
        st.markdown(f"#### {ce.canonical_name} ({ce.entity_type})")
        st.markdown(f"**Canonical ID:** {ce.canonical_id}")
        st.markdown(f"**Aliases:** {', '.join(sorted(ce.aliases))}")
        st.markdown(f"**Case IDs:** {', '.join(sorted(ce.case_ids))}")
        st.markdown("**Source records:**")
        for rec in ce.source_records:
            st.write(rec)


def main():
    st.set_page_config(page_title="threadVault", layout="wide", initial_sidebar_state="expanded")
    _local_style()

    # Header
    st.markdown("""
    <div style='display:flex; align-items:center; justify-content:space-between'>
      <div>
        <h1 style='margin:0; color:#e6eef3'>threadVault</h1>
        <div style='color:#cbd5e1'>AI-Powered Investigation Intelligence</div>
      </div>
      <div style='color:#cbd5e1; max-width:600px; text-align:right'>
        threadVault connects fragmented investigation records into a single visual network, helping investigators identify relationships, patterns and leads for human review.
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.header("Investigator (Demo)")
        officer = st.selectbox("Select demo officer", ["Officer_A (Demo)", "Officer_B (Demo)"])
        if st.button("Record demo login"):
            append_audit_event("login", "--", officer, {"note": "demo login"})
            st.success(f"Logged in as {officer}")

        st.markdown("---")
        st.header("Case Selector")
        case_options = get_available_cases()
        if not case_options:
            st.warning("No synthetic case data is currently available.")
            return
        selected_case = st.selectbox("Select case", case_options, index=0)
        st.markdown("---")
        q = st.text_input("Search people, organizations, locations...")

    # Build backend artifacts and UI sections
    proc = process_case(selected_case)
    case_data = load_case(selected_case)
    G = build_case_graph(selected_case)
    ranking = analyze_case_graph(G)
    patterns = explain_patterns(selected_case)
    timeline = get_investigation_timeline(selected_case)

    # Case Brief
    counts = case_data.get("counts", {})
    title = "Investigation"
    if counts.get("transactions", 0) >= max(counts.get("cdr", 0), counts.get("social", 0), counts.get("fir", 0)) and counts.get("transactions", 0) > 0:
        title = "Potential financial and association network"
    elif counts.get("social", 0) > 0:
        title = "Social association case"
    key_influencer = ranking[0].get("canonical_name", "No ranked entity") if ranking else "No ranked entity"
    source_types = [source.upper() for source, count in counts.items() if count > 0]
    st.markdown(
        f"""
        <div class='brief-card'>
          <div class='brief-kicker'>Case {selected_case}</div>
          <div class='brief-title'>{title}</div>
          <div class='muted'>Inferred summary from available case sources</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    brief_cols = st.columns(5)
    brief_cols[0].metric("Entities", str(G.number_of_nodes()))
    brief_cols[1].metric("Connections", str(G.number_of_edges()))
    brief_cols[2].metric("Investigative leads", str(len(patterns)))
    brief_cols[3].metric("Data sources", str(len(source_types)))
    brief_cols[4].markdown(f"<div class='eyebrow'>Key person</div><div class='brief-title'>{key_influencer}</div>", unsafe_allow_html=True)
    st.caption(f"Sources present: {' · '.join(source_types)}")

    st.markdown("---")

    # Main layout: network left, entity panel right
    left, right = st.columns([4, 1])
    with left:
        st.markdown("## Relationship Network")
        net_html = create_network_html(selected_case, height=900)
        # Render the vis-network HTML using the components API (interactive)
        components.html(net_html, height=920, scrolling=True)

    # Entity selection and details
    node_map = {n: d.get("canonical_name") for n, d in G.nodes(data=True)}
    selected_entity = None
    with right:
        st.markdown("### Selected Entity")
        options = ["-- none --"] + [f"{nid} | {name}" for nid, name in node_map.items()]
        sel = st.selectbox("Select entity", options)
        if sel and sel != "-- none --":
            cid = sel.split("|", 1)[0].strip()
            selected_entity = cid
            # display entity details
            node = G.nodes[cid]
            entity_name = node.get("canonical_name") or cid
            entity_type = str(node.get("entity_type") or "Unknown").title()
            st.markdown(f"<div class='entity-card'><div class='brief-title'>{entity_name}</div><div class='muted'>{entity_type}</div>", unsafe_allow_html=True)
            # influence rank
            inf_map = {r['canonical_id']: r for r in ranking}
            inf = inf_map.get(cid)
            level = "High" if inf and inf['influence_score'] >= 0.15 else ("Medium" if inf and inf['influence_score'] >= 0.06 else "Low")
            st.markdown(f"**Network importance:** {level}")
            # connections
            neighbors = list(G.neighbors(cid))
            st.markdown(f"**Connections:** {len(neighbors)}")
            # data sources and aliases from canonical entities
            canonical = proc['canonical_entities']
            ce = canonical.get(cid)
            if ce:
                srcs = sorted({r.get('source') for r in ce.source_records if isinstance(r, dict) and r.get('source')}) if ce.source_records else []
                st.markdown(f"**Data sources:** {' · '.join([s.upper() for s in srcs]) if srcs else 'N/A'}")
                st.markdown("**Aliases**")
                for a in sorted(set(ce.aliases)):
                    st.markdown(f"- {a}")
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("**Connected Entities**")
            # show formatted connections with investigator-friendly relationship names
            for n2 in neighbors:
                edge_data = G.get_edge_data(cid, n2) or {}
                rtype = edge_data.get('relationship_type')
                if rtype:
                    display_type = {'CALLED': 'CALL', 'TAGGED_WITH': 'ASSOCIATED_WITH'}.get(rtype, rtype)
                    icon = {'CALL': '📞', 'PAID': '💰', 'SEEN_AT': '📍'}.get(display_type, '🔗')
                    record_id = edge_data.get('record_id')
                    evidence = f" · Evidence: {record_id}" if record_id else ""
                    st.markdown(f"**{entity_name}**<br>{icon} {display_type}<br>**{G.nodes[n2].get('canonical_name') or n2}**{evidence}", unsafe_allow_html=True)

    st.markdown("---")

    # Investigative Leads
    st.markdown("## Investigative Leads")
    # map technical pattern names to human-readable titles
    pattern_map = {
        'CALL_FOLLOWED_BY_TRANSACTION': 'Call followed by payment',
        'HIGH_CALL_FREQUENCY': 'Unusually frequent calls',
        'HIGH_CONNECTIVITY': 'Highly connected entity',
        'CROSS_SOURCE_PRESENCE': 'Appears across multiple data sources',
        'HIGH_TRANSACTION_VALUE': 'Unusually large transaction',
    }
    if patterns:
        for p in patterns:
            sev = str(p.get('severity', 'LOW')).upper()
            color = '#d53e4f' if sev == 'HIGH' else ('#f0ad4e' if sev == 'MEDIUM' else '#2ca02c')
            tech = p.get('pattern_type') or 'INVESTIGATIVE_LEAD'
            title = pattern_map.get(tech, str(tech).replace('_', ' ').title())
            entities = list(dict.fromkeys(p.get('entities_involved') or []))
            display_entities = [node_map.get(entity, entity) for entity in entities]
            evidence = p.get('evidence') or []
            if isinstance(evidence, dict):
                evidence = [value for key, value in evidence.items() if key.endswith('_id')]
            evidence_text = ' · '.join(str(item) for item in evidence)
            icon = '📞 → 💰' if tech == 'CALL_FOLLOWED_BY_TRANSACTION' else '🔎'
            with st.container():
                st.markdown(f"<div class='lead-card {sev.lower()}'><div class='lead-severity' style='color:{color}'>{sev} PRIORITY</div><div class='lead-title'>{icon} {title}</div>", unsafe_allow_html=True)
                st.markdown(f"**Entities involved:** {' ↔ '.join(str(entity) for entity in display_entities)}")
                st.markdown(f"**Why this matters:** {p.get('why') or p.get('explanation')}")
                st.markdown(f"**Evidence:** {evidence_text or 'Recorded case evidence'}")
                with st.expander('Technical details'):
                    st.write(f"Rule: {tech}")
                    st.write(p)
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.write("No investigative leads for this case.")

    st.markdown("---")

    # Timeline
    st.markdown("## Investigation Timeline")
    if timeline:
        for ev in timeline:
            timestamp = str(ev.get('timestamp') or 'Unknown time')
            date, _, time = timestamp.partition('T')
            if not time:
                date, _, time = timestamp.partition(' ')
            event_type = str(ev.get('event_type') or 'EVENT')
            icon = {'CALL': '📞', 'TRANSACTION': '💰', 'SOCIAL': '💬', 'FIR': '📄'}.get(event_type, '🔎')
            entities = [str(entity) for entity in (ev.get('entities') or []) if entity]
            actors = ' · '.join(entities) if entities else 'Not specified'
            record_id = ev.get('record_id')
            st.markdown(
                f"<div class='timeline-card'><div class='timeline-date'>{date} {time}</div><div class='timeline-type'>{icon} {event_type}</div><div><strong>Actors:</strong> {actors}</div><div>{ev.get('description') or 'No description available.'}</div><div class='muted'>Record: {record_id or 'N/A'}</div></div>",
                unsafe_allow_html=True,
            )
    else:
        st.write("No timeline events available.")

    # Technical details / Audit
    with st.expander("Technical Network Analysis"):
        st.write("Network influence combines connection count, bridge position and overall network importance.")
        df_rank = pd.DataFrame(ranking)
        if not df_rank.empty:
            df_rank_display = df_rank[["canonical_name", "entity_type", "degree", "betweenness", "pagerank", "influence_score"]].copy()
            df_rank_display = df_rank_display.rename(columns={
                'degree': 'Connections',
                'betweenness': 'Network Bridge',
                'pagerank': 'Network Importance',
                'influence_score': 'Investigative Influence'
            })
            st.dataframe(df_rank_display)

    with st.expander("Audit Log"):
        if st.button("Append demo audit event"):
            ev = append_audit_event("view_case", selected_case, officer, {"note": "viewed case in UI"})
            st.success("Audit event recorded")
        verified = verify_audit_chain()
        st.markdown(f"Integrity: {'VERIFIED' if verified else 'FAILED'}")
        logs = get_audit_log(10)
        for r in logs[::-1]:
            st.markdown(f"- {r.get('timestamp')} | {r.get('actor')} | {r.get('action')} | {r.get('case_id')}")

    # Search handling
    if q:
        ql = q.lower()
        matches = [nid for nid, name in node_map.items() if ql in (name or '').lower()]
        if matches:
            st.info(f"Search found {len(matches)} entity(ies). Selecting first match.")
            # programmatic select via placeholder - reload selection
            first = matches[0]
            if hasattr(st, "query_params"):
                st.query_params["selected"] = first
            else:
                st.experimental_set_query_params(selected=first)



if __name__ == "__main__":
    main()
