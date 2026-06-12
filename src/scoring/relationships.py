"""
Relationship-based investment signal scoring.

Computes dependency risk, competitive positioning, influence metrics,
multi-hop paths, and plain-English investment insights from the curated
company relationship graph + live batch metrics.

Grounded in academic research:
  - Supply chain contagion multiplier ~1.94x (Chicago Booth / JFQA)
  - Customer momentum = 56 bps/month alpha (Chicago Booth)
  - Centrality-weighted factors improve Sharpe from 0.35 → 0.71 (FactSet)
  - Vulnerability / systemicness metrics (SDA Bocconi)
  - Multi-hop relationships contain alpha up to 4th degree (J. Portfolio Mgmt)
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_health(ticker: str, metrics_data: dict) -> tuple[Optional[int], str]:
    """Safely extract health for a ticker.

    Returns (score_0_100, verdict_str).  Score is None when no data is available.
    quick_health scores (0-10) are scaled to 0-100 for dashboard consistency.
    """
    entry = metrics_data.get(ticker) or {}
    qh = entry.get("quick_health") or {}
    raw = qh.get("score")
    verdict = qh.get("verdict", "N/A")
    if raw is None:
        return None, verdict
    return min(100, max(0, int(raw) * 10)), verdict


# ---------------------------------------------------------------------------
# Dependency scoring (supply-chain vulnerability)
# ---------------------------------------------------------------------------

def compute_dependency_score(
    ticker: str,
    relationships: list[dict],
    metrics_data: dict,
) -> dict:
    """How healthy are the companies this ticker depends on?

    A ticker 'depends on' another company when it is the SOURCE of a
    supplier or customer relationship — in both cases the source relies
    on the target for goods, services, or revenue.

    Returns a dict suitable for display and insight generation.
    """
    deps: list[dict] = []  # companies this ticker depends on
    for rel in relationships:
        if rel["source"].upper() == ticker.upper() and rel["type"] in ("supplier", "customer", "partner"):
            deps.append({"ticker": rel["target"], "type": rel["type"], "strength": rel.get("strength", "medium")})
        # Also capture reverse: if ticker is the target of a customer rel,
        # the source is a customer that depends on ticker for revenue.
        # For dependency scoring we only care about who the ticker RELIES ON,
        # so we skip the reverse direction here.

    if not deps:
        return {
            "score": None,
            "verdict": "No Dependencies",
            "supplier_count": 0,
            "supplier_health_avg": None,
            "weak_suppliers": [],
            "concentration_risk": "N/A",
        }

    health_scores: list[int] = []
    weak: list[dict] = []
    for d in deps:
        score, verdict = _get_health(d["ticker"], metrics_data)
        d["health_score"] = score
        d["health_verdict"] = verdict
        if score is not None:
            health_scores.append(score)

    avg_health = round(sum(health_scores) / len(health_scores)) if health_scores else None

    # Weak suppliers: health < 40 (Weak on 0-100 scale)
    weak = [d for d in deps if d.get("health_score") is not None and d["health_score"] < 40]

    # Concentration risk: >50% of dependencies are with a single company
    ticker_counts: dict[str, int] = {}
    for d in deps:
        ticker_counts[d["ticker"]] = ticker_counts.get(d["ticker"], 0) + 1
    max_share = max(ticker_counts.values()) / len(deps) if deps else 0
    concentration = "High" if max_share > 0.5 else ("Medium" if max_share > 0.33 else "Low")

    # Verdict
    if avg_health is None:
        verdict = "Unknown"
        score = None
    elif weak and len(weak) >= len(deps) * 0.5:
        verdict = "Vulnerable"
        score = max(0, avg_health - 25)
    elif weak:
        verdict = "Moderate Risk"
        score = max(0, avg_health - 10)
    elif avg_health >= 70:
        verdict = "Resilient"
        score = avg_health
    else:
        verdict = "Moderate Risk"
        score = avg_health

    return {
        "score": score,
        "verdict": verdict,
        "supplier_count": len(deps),
        "supplier_health_avg": avg_health,
        "weak_suppliers": weak,
        "concentration_risk": concentration,
        "dependencies": deps,
    }


# ---------------------------------------------------------------------------
# Influence scoring (systemicness — how many depend on this node?)
# ---------------------------------------------------------------------------

def compute_influence_score(
    ticker: str,
    relationships: list[dict],
    _metrics_data: dict,
) -> dict:
    """How many companies depend on this ticker?

    A company is 'depended on' when it is the TARGET of a supplier or
    customer relationship — others rely on it for goods/services/revenue.
    """
    dependents: list[dict] = []
    for rel in relationships:
        # ticker is the target → source relies on ticker
        if rel["target"].upper() == ticker.upper() and rel["type"] in ("supplier", "customer", "partner"):
            dependents.append({"ticker": rel["source"], "type": rel["type"], "strength": rel.get("strength", "medium")})

    if not dependents:
        return {
            "score": None,
            "verdict": "Limited Impact",
            "dependent_count": 0,
            "dependents": [],
        }

    # Count unique dependents
    unique_deps = list({d["ticker"]: d for d in dependents}.values())
    strong_count = sum(1 for d in unique_deps if d.get("strength") == "strong")

    if len(unique_deps) >= 4:
        verdict = "Critical Node"
        score = min(100, 60 + len(unique_deps) * 5 + strong_count * 5)
    elif len(unique_deps) >= 2:
        verdict = "Influential"
        score = 40 + len(unique_deps) * 5 + strong_count * 3
    else:
        verdict = "Limited Impact"
        score = 20 + strong_count * 10

    return {
        "score": min(100, score),
        "verdict": verdict,
        "dependent_count": len(unique_deps),
        "strong_dependency_count": strong_count,
        "dependents": unique_deps,
    }


# ---------------------------------------------------------------------------
# Competitive positioning
# ---------------------------------------------------------------------------

def compute_competitive_position(
    ticker: str,
    relationships: list[dict],
    metrics_data: dict,
) -> Optional[dict]:
    """Rank this ticker among its competitors in the relationship graph.

    Only returns a result when the ticker has at least one competitor
    relationship in the current group.
    """
    competitors: list[dict] = []
    for rel in relationships:
        if rel["type"] != "competitor":
            continue
        if rel["source"].upper() == ticker.upper():
            competitors.append({"ticker": rel["target"], "desc": rel.get("description", "")})
        elif rel["target"].upper() == ticker.upper():
            competitors.append({"ticker": rel["source"], "desc": rel.get("description", "")})

    if not competitors:
        return None

    # Score ourselves + competitors
    my_score, my_verdict = _get_health(ticker, metrics_data)
    scored = [(ticker, my_score, my_verdict)]
    for c in competitors:
        s, v = _get_health(c["ticker"], metrics_data)
        scored.append((c["ticker"], s, v))

    # Rank by health score descending (None sorts last)
    ranked = sorted(scored, key=lambda x: (x[1] is None, -(x[1] or 0)))

    my_rank = next(i + 1 for i, (t, _, _) in enumerate(ranked) if t.upper() == ticker.upper())
    leader_ticker, leader_score, _ = ranked[0]
    laggard_ticker, laggard_score, _ = ranked[-1]

    valid_scores = [s for _, s, _ in ranked if s is not None]
    avg_score = round(sum(valid_scores) / len(valid_scores)) if valid_scores else None

    health_delta = None
    if my_score is not None and avg_score is not None:
        health_delta = my_score - avg_score

    # Pair trade idea: leader is strong (>=70), laggard is weak (<40), gap >= 30
    pair_trade = None
    if (
        leader_score is not None
        and laggard_score is not None
        and leader_score >= 70
        and laggard_score < 40
        and (leader_score - laggard_score) >= 30
        and leader_ticker.upper() != laggard_ticker.upper()
    ):
        pair_trade = {
            "long": leader_ticker,
            "short": laggard_ticker,
            "gap": leader_score - laggard_score,
        }

    return {
        "rank": my_rank,
        "total": len(ranked),
        "leader": leader_ticker,
        "leader_score": leader_score,
        "laggard": laggard_ticker,
        "laggard_score": laggard_score,
        "health_delta_vs_avg": health_delta,
        "competitor_avg_health": avg_score,
        "pair_trade": pair_trade,
        "competitors": [{"ticker": c["ticker"], "desc": c["desc"]} for c in competitors],
    }


# ---------------------------------------------------------------------------
# Multi-hop path finding
# ---------------------------------------------------------------------------

def find_multi_hop_paths(
    ticker: str,
    relationships: list[dict],
    max_depth: int = 2,
) -> list[dict]:
    """Find all paths up to max_depth hops from ticker through the relationship graph.

    Returns list of {path: [ticker, ...], description: str, types: [str, ...]}.
    """
    # Build adjacency: ticker → [(neighbor, rel_type, description, strength)]
    adj: dict[str, list[tuple[str, str, str, str]]] = {}
    for rel in relationships:
        s, t = rel["source"].upper(), rel["target"].upper()
        rtype = rel["type"]
        desc = rel.get("description", "")
        strength = rel.get("strength", "medium")
        adj.setdefault(s, []).append((t, rtype, desc, strength))
        adj.setdefault(t, []).append((s, rtype, desc, strength))

    ticker_u = ticker.upper()
    if ticker_u not in adj:
        return []

    paths: list[dict] = []
    visited_start = {ticker_u}

    for hop1, rtype1, desc1, strength1 in adj[ticker_u]:
        paths.append({
            "path": [ticker, hop1],
            "depth": 1,
            "description": desc1,
            "types": [rtype1],
            "strengths": [strength1],
        })

        if max_depth < 2:
            continue

        if hop1 not in adj:
            continue

        for hop2, rtype2, desc2, strength2 in adj[hop1]:
            if hop2 in visited_start or hop2 == ticker_u:
                continue
            paths.append({
                "path": [ticker, hop1, hop2],
                "depth": 2,
                "description": f"{desc1} → {desc2}",
                "types": [rtype1, rtype2],
                "strengths": [strength1, strength2],
            })

    return paths


# ---------------------------------------------------------------------------
# Group-level ecosystem summary
# ---------------------------------------------------------------------------

def compute_ecosystem_summary(
    relationships: list[dict],
    metrics_data: dict,
) -> dict:
    """Compute aggregate ecosystem health for the entire relationship group.

    Returns counts and averages by relationship role.
    """
    # Collect all unique tickers
    all_tickers: set[str] = set()
    for rel in relationships:
        all_tickers.add(rel["source"].upper())
        all_tickers.add(rel["target"].upper())

    # Aggregate health
    health_scores: list[int] = []
    strong_count = moderate_count = weak_count = unknown_count = 0
    for t in all_tickers:
        score, verdict = _get_health(t, metrics_data)
        if score is not None:
            health_scores.append(score)
        if verdict == "Strong":
            strong_count += 1
        elif verdict == "Moderate":
            moderate_count += 1
        elif verdict == "Weak":
            weak_count += 1
        else:
            unknown_count += 1

    avg_health = round(sum(health_scores) / len(health_scores)) if health_scores else None

    # Competitive field metrics
    comp_tickers: set[str] = set()
    for rel in relationships:
        if rel["type"] == "competitor":
            comp_tickers.add(rel["source"].upper())
            comp_tickers.add(rel["target"].upper())

    comp_scores = []
    comp_leader = comp_laggard = None
    comp_leader_score = comp_laggard_score = None
    for t in comp_tickers:
        score, _ = _get_health(t, metrics_data)
        if score is not None:
            comp_scores.append(score)
            if comp_leader_score is None or score > comp_leader_score:
                comp_leader_score = score
                comp_leader = t
            if comp_laggard_score is None or score < comp_laggard_score:
                comp_laggard_score = score
                comp_laggard = t

    # Critical nodes (most depended-on)
    influence_counts: dict[str, int] = {}
    for rel in relationships:
        if rel["type"] in ("supplier", "customer", "partner"):
            influence_counts[rel["target"]] = influence_counts.get(rel["target"], 0) + 1
    critical = sorted(influence_counts.items(), key=lambda x: -x[1])[:3]

    return {
        "total_companies": len(all_tickers),
        "avg_health": avg_health,
        "strong_count": strong_count,
        "moderate_count": moderate_count,
        "weak_count": weak_count,
        "unknown_count": unknown_count,
        "competitor_count": len(comp_tickers),
        "competitor_leader": comp_leader,
        "competitor_leader_score": comp_leader_score,
        "competitor_laggard": comp_laggard,
        "competitor_laggard_score": comp_laggard_score,
        "critical_nodes": [{"ticker": t, "dependents": c} for t, c in critical],
    }


# ---------------------------------------------------------------------------
# Investment insight generation (the master function)
# ---------------------------------------------------------------------------

def generate_relationship_insights(
    relationships: list[dict],
    metrics_data: dict,
) -> list[dict]:
    """Generate ranked, deduplicated investment insights from relationships.

    Each insight is a dict with:
      category:   "risk" | "opportunity" | "positioning" | "dependency" | "positive"
      priority:   1 (critical) | 2 (notable) | 3 (informational)
      headline:   plain-English one-liner
      detail:     1-2 sentence explanation
      tickers:    involved tickers
      action:     suggested next step for the investor
    """
    insights: list[dict] = []
    seen: set[str] = set()  # dedup key

    def _dedup_key(*parts: str) -> str:
        return "|".join(sorted(p.upper() for p in parts))

    # --- 1. Supply chain risk & opportunity insights ---
    for rel in relationships:
        src, tgt = rel["source"], rel["target"]
        rtype = rel["type"]
        desc = rel.get("description", "")

        src_score, src_verd = _get_health(src, metrics_data)
        tgt_score, tgt_verd = _get_health(tgt, metrics_data)

        # --- Supplier risk: source depends on target that is Weak ---
        if rtype == "supplier" and src_score is not None and tgt_score is not None:
            if tgt_verd == "Weak" and src_verd in ("Strong", "Moderate"):
                key = _dedup_key(src, tgt, "supplier_risk")
                if key not in seen:
                    seen.add(key)
                    insights.append({
                        "category": "risk",
                        "priority": 1,
                        "headline": f"{src} depends on {tgt} for critical supply — {tgt} shows Weak health",
                        "detail": (
                            f"{src} (Health: {src_verd} {src_score}/100) relies on {tgt} "
                            f"(Health: {tgt_verd} {tgt_score}/100) as a supplier. "
                            f"{desc} A disruption at {tgt} could directly impact {src}'s operations."
                        ),
                        "tickers": [src, tgt],
                        "action": f"Monitor {tgt} earnings and supply chain news. Consider reducing {src} exposure if {tgt} deteriorates further.",
                    })

            elif tgt_verd == "Strong" and src_verd == "Strong":
                key = _dedup_key(src, tgt, "supplier_strong")
                if key not in seen:
                    seen.add(key)
                    insights.append({
                        "category": "positive",
                        "priority": 3,
                        "headline": f"{src} and supplier {tgt} are both Strong — supply chain is healthy",
                        "detail": (
                            f"{src} ({src_score}/100) relies on {tgt} ({tgt_score}/100). "
                            f"Both companies show solid financial health — this supply relationship "
                            f"appears stable."
                        ),
                        "tickers": [src, tgt],
                        "action": f"For supply-chain exposure to {src}'s growth, {tgt} offers a supplier-play alternative.",
                    })

        # --- Customer risk ---
        if rtype == "customer" and src_score is not None and tgt_score is not None:
            if src_verd == "Weak":
                key = _dedup_key(src, tgt, "customer_risk")
                if key not in seen:
                    seen.add(key)
                    insights.append({
                        "category": "risk",
                        "priority": 2,
                        "headline": f"{tgt}'s customer {src} shows Weak health — demand may soften",
                        "detail": (
                            f"{src} (Health: {src_verd} {src_score}/100) is a customer of {tgt} "
                            f"({tgt_verd} {tgt_score}/100). Weakness in {src} could reduce "
                            f"future orders, impacting {tgt}'s revenue."
                        ),
                        "tickers": [src, tgt],
                        "action": f"Watch {src}'s earnings for demand signals that could affect {tgt}.",
                    })

        # --- Competitive gaps ---
        if rtype == "competitor" and src_score is not None and tgt_score is not None:
            delta = abs(src_score - tgt_score)
            if delta >= 30:
                stronger = src if src_score > tgt_score else tgt
                weaker = tgt if src_score > tgt_score else src
                stronger_s, weaker_s = (src_score, tgt_score) if src_score > tgt_score else (tgt_score, src_score)
                key = _dedup_key(src, tgt, "comp_gap")
                if key not in seen:
                    seen.add(key)
                    insights.append({
                        "category": "opportunity",
                        "priority": 2,
                        "headline": f"Competitive gap: {stronger} ({stronger_s}/100) leads {weaker} ({weaker_s}/100) by {delta} points",
                        "detail": (
                            f"{stronger} shows significantly stronger financial health than {weaker}. "
                            f"{desc} In a competitive market, the stronger player often gains share."
                        ),
                        "tickers": [src, tgt],
                        "action": f"Potential pair trade: Long {stronger}, Short {weaker} — or simply favor {stronger} over {weaker}.",
                    })

    # --- 2. Multi-hop dependency insights ---
    all_tickers: set[str] = set()
    for rel in relationships:
        all_tickers.add(rel["source"])
        all_tickers.add(rel["target"])

    critical_paths_found = 0
    for ticker in sorted(all_tickers):
        if critical_paths_found >= 3:
            break
        paths = find_multi_hop_paths(ticker, relationships, max_depth=2)
        for p in paths:
            if p["depth"] < 2:
                continue
            if critical_paths_found >= 3:
                break
            # Check if there's a supply chain relationship (supplier/customer at each hop)
            types = p["types"]
            if all(t in ("supplier", "customer") for t in types):
                # Get health at each hop
                hop_healths = []
                for hop in p["path"]:
                    s, v = _get_health(hop, metrics_data)
                    hop_healths.append(f"{hop} ({v} {s}/100)" if s else f"{hop} (N/A)")

                # Only flag if there's a weak link
                has_weak = any("Weak" in h for h in hop_healths)
                key = _dedup_key(*p["path"], "multihop")
                if key not in seen and has_weak:
                    seen.add(key)
                    critical_paths_found += 1
                    insights.append({
                        "category": "dependency",
                        "priority": 1,
                        "headline": f"Critical path: {' → '.join(p['path'])}",
                        "detail": (
                            f"Hidden dependency chain — {' relies on '.join(p['path'])}. "
                            f"Health along chain: {' | '.join(hop_healths)}. "
                            f"A problem at any link cascades through the entire chain "
                            f"(research shows supply chain shocks have a ~1.94× multiplier effect)."
                        ),
                        "tickers": p["path"],
                        "action": f"Map your portfolio exposure to all companies in this chain.",
                    })

    # --- 3. Critical node insights ---
    ecosystem = compute_ecosystem_summary(relationships, metrics_data)
    for node_info in ecosystem.get("critical_nodes", [])[:2]:
        ticker = node_info["ticker"]
        deps = node_info["dependents"]
        score, verd = _get_health(ticker, metrics_data)
        key = _dedup_key(ticker, "critical_node")
        if key not in seen and deps >= 3:
            seen.add(key)
            health_note = f"Health: {verd} {score}/100. " if score else ""
            insights.append({
                "category": "dependency",
                "priority": 2,
                "headline": f"{ticker} is a critical node — {deps} companies depend on it",
                "detail": (
                    f"{ticker} is a key supplier/partner to {deps} companies in this group. "
                    f"{health_note}"
                    f"As a bottleneck, any disruption at {ticker} would ripple across the entire ecosystem."
                ),
                "tickers": [ticker],
                "action": f"Monitor {ticker} closely — it is a bellwether for the entire group.",
            })

    # --- 4. Competitive positioning insights (per ticker) ---
    for ticker in sorted(all_tickers):
        pos = compute_competitive_position(ticker, relationships, metrics_data)
        if pos is None or pos["total"] < 2:
            continue
        key = _dedup_key(ticker, "positioning")
        if key in seen:
            continue
        seen.add(key)

        # Only highlight when there's a meaningful lead (delta >= 10 vs avg)
        delta = pos.get("health_delta_vs_avg")
        if pos["rank"] == 1 and delta is not None and delta >= 10:
            insights.append({
                "category": "positioning",
                "priority": 3,
                "headline": f"{ticker} leads {pos['total']} competitors in financial health",
                "detail": (
                    f"Ranked #{pos['rank']} of {pos['total']} with health score "
                    f"{_get_health(ticker, metrics_data)[0]}/100 vs competitor average of "
                    f"{pos['competitor_avg_health']}/100."
                ),
                "tickers": [ticker],
                "action": f"{ticker} is the strongest company in its competitive set.",
            })

        if pos.get("pair_trade"):
            pt = pos["pair_trade"]
            key2 = _dedup_key(pt["long"], pt["short"], "pair")
            if key2 not in seen:
                seen.add(key2)
                insights.append({
                    "category": "opportunity",
                    "priority": 2,
                    "headline": f"Pair trade idea: Long {pt['long']}, Short {pt['short']} ({pt['gap']}pt health gap)",
                    "detail": (
                        f"{pt['long']} is the strongest competitor while {pt['short']} is the weakest. "
                        f"A {pt['gap']}-point health gap suggests divergent trajectories in the same market."
                    ),
                    "tickers": [pt["long"], pt["short"]],
                    "action": f"Consider a market-neutral pair trade: Long {pt['long']}, Short {pt['short']}.",
                })

    # Sort: priority 1 first, then priority 2, then 3
    insights.sort(key=lambda x: x["priority"])
    return insights
