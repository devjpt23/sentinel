"""
Custom Alert Builder UI for the Sentinel dashboard.

Renders the rule creation form, rule list, and rule editing interface.
Follows the existing render_* pattern in src/display/notifications.py.

Usage:
    from src.display.custom_alerts import render_custom_alerts_page
    render_custom_alerts_page()
"""

import json
import streamlit as st
from typing import Optional, Dict

from src.data.notification_db import (
    get_custom_alert_rules,
    get_custom_alert_rule_by_id,
    create_custom_alert_rule,
    update_custom_alert_rule,
    delete_custom_alert_rule,
    toggle_custom_alert_rule,
)
from src.notifications.custom_alerts import (
    SIGNAL_CATALOG,
    get_signal_categories,
    get_signals_by_category,
    describe_condition_for_ui,
)

# ─── Severity Display ─────────────────────────────────────────

_SEVERITY_COLORS = {
    "info": "#58A6FF",
    "warning": "#D29922",
    "critical": "#DA3633",
}

_SEVERITY_ICONS = {
    "info": "ℹ️",
    "warning": "⚠️",
    "critical": "🚨",
}


# ─── Main Page ────────────────────────────────────────────────

def render_custom_alerts_page() -> None:
    """Render the Custom Alerts page (full-page, called from app.py routing)."""
    user = st.session_state.get("user")
    if not user:
        st.warning("Sign in to create and manage custom alerts.")
        return

    st.markdown(
        '<h2 style="color: #58A6FF;">⚡ Custom Alert Builder</h2>'
        '<p style="color: #8B949E; margin-bottom: 24px;">'
        'Create your own notification rules. Choose from price, technical, and '
        'fundamental signals — Sentinel checks them every cycle and notifies you '
        'when conditions are met.</p>',
        unsafe_allow_html=True,
    )

    tab1, tab2 = st.tabs(["📋 My Rules", "➕ Create Rule"])

    with tab1:
        _render_rule_list(user)

    with tab2:
        _render_rule_form(user)


# ─── Rule List ────────────────────────────────────────────────

def _render_rule_list(user: Dict) -> None:
    """Show all the user's custom alert rules as cards."""
    rules = get_custom_alert_rules(user["id"], enabled_only=False)

    if not rules:
        st.markdown(
            '<div style="background: #161B22; border: 1px solid #21262D; '
            'border-radius: 8px; padding: 32px; text-align: center; margin-top: 16px;">'
            '<p style="color: #8B949E; font-size: 1.1rem; margin-bottom: 8px;">'
            '📭 No custom alerts yet</p>'
            '<p style="color: #484F58; font-size: 0.85rem;">'
            'Switch to the <strong>Create Rule</strong> tab to build your first alert.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<p style="color: #8B949E; font-size: 0.8rem; margin-bottom: 12px;">'
        f'{len(rules)} rule{"s" if len(rules) != 1 else ""}</p>',
        unsafe_allow_html=True,
    )

    for rule in rules:
        _render_rule_card(rule)


def _render_rule_card(rule: Dict) -> None:
    """Render a single custom alert rule as a card."""
    rule_id = rule["id"]
    enabled = bool(rule.get("enabled", 1))
    severity = rule.get("severity", "info")
    scope = rule.get("scope", "watchlist")
    ticker = rule.get("ticker", "")
    logic_op = rule.get("logic_operator", "AND")

    sev_color = _SEVERITY_COLORS.get(severity, "#58A6FF")
    sev_icon = _SEVERITY_ICONS.get(severity, "ℹ️")

    # Parse conditions for display
    try:
        conditions = json.loads(rule.get("conditions", "[]"))
    except (json.JSONDecodeError, TypeError):
        conditions = []

    # Build condition summary
    cond_parts = []
    for c in conditions:
        desc = describe_condition_for_ui(c)
        cond_parts.append(desc)

    connector = f" <span style='color: #8B949E;'>AND</span> " if logic_op == "AND" else f" <span style='color: #8B949E;'>OR</span> "
    cond_summary = connector.join(cond_parts) if cond_parts else "No conditions"

    # Scope badge
    if scope == "watchlist":
        scope_badge = '<span style="background: #1F2937; color: #58A6FF; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem;">📋 Watchlist</span>'
    else:
        scope_badge = f'<span style="background: #1F2937; color: #58A6FF; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem;">📌 {ticker}</span>'

    # Enabled badge
    enabled_badge = (
        '<span style="background: #1B3826; color: #3FB950; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem;">● Active</span>'
        if enabled
        else '<span style="background: #3D1F1F; color: #F85149; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem;">○ Paused</span>'
    )

    opacity = "" if enabled else "opacity: 0.55;"

    st.markdown(
        f'<div style="background: #161B22; border: 1px solid #21262D; '
        f'border-left: 3px solid {sev_color}; border-radius: 6px; '
        f'padding: 16px; margin-bottom: 12px; {opacity}">'
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start;">'
        f'<div>'
        f'<span style="color: #E6EDF3; font-weight: 600; font-size: 1rem;">'
        f'{sev_icon} {rule["name"]}</span>'
        f'<div style="margin-top: 6px;">{scope_badge} {enabled_badge} '
        f'<span style="color: {sev_color}; font-size: 0.7rem;">{severity.upper()}</span></div>'
        f'</div>'
        f'</div>'
        f'<p style="color: #8B949E; font-size: 0.82rem; margin-top: 10px; '
        f'line-height: 1.5;">When: {cond_summary}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Action buttons
    col1, col2, col3, _ = st.columns([1, 1, 1, 3])

    with col1:
        new_state = not enabled
        label = "Enable" if new_state else "Disable"
        if st.button(label, key=f"toggle_{rule_id}", use_container_width=True):
            toggle_custom_alert_rule(rule_id, new_state)
            st.rerun()

    with col2:
        if st.button("✏️ Edit", key=f"edit_{rule_id}", use_container_width=True):
            st.session_state.editing_rule_id = rule_id
            st.session_state.active_tab = 1  # Switch to Create Rule tab
            st.rerun()

    with col3:
        if st.button("🗑️ Delete", key=f"del_{rule_id}", use_container_width=True):
            st.session_state.confirm_delete_id = rule_id
            st.rerun()

    # Delete confirmation
    if st.session_state.get("confirm_delete_id") == rule_id:
        st.warning(f"Delete **{rule['name']}**? This cannot be undone.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, Delete", key=f"confirm_del_{rule_id}", use_container_width=True):
                delete_custom_alert_rule(rule_id)
                st.session_state.pop("confirm_delete_id", None)
                st.success(f"Deleted '{rule['name']}'")
                st.rerun()
        with c2:
            if st.button("Cancel", key=f"cancel_del_{rule_id}", use_container_width=True):
                st.session_state.pop("confirm_delete_id", None)
                st.rerun()


# ─── Rule Form (Create / Edit) ────────────────────────────────

def _render_rule_form(user: Dict, existing_rule: Optional[Dict] = None) -> None:
    """Render the rule creation/editing form."""
    # Check if we're editing an existing rule
    editing_id = st.session_state.get("editing_rule_id")
    if editing_id and existing_rule is None:
        existing_rule = get_custom_alert_rule_by_id(editing_id)
        if existing_rule is None:
            st.session_state.pop("editing_rule_id", None)

    is_editing = existing_rule is not None
    form_title = "✏️ Edit Rule" if is_editing else "➕ Create New Rule"

    st.markdown(
        f'<h3 style="color: #E6EDF3; margin-top: 16px;">{form_title}</h3>',
        unsafe_allow_html=True,
    )

    # Rule name
    rule_name = st.text_input(
        "Rule Name",
        value=existing_rule.get("name", "") if is_editing else "",
        placeholder="e.g., AAPL Oversold Bounce",
        max_chars=50,
        key="rule_name",
    )

    col1, col2 = st.columns(2)

    with col1:
        severity = st.selectbox(
            "Severity",
            options=["info", "warning", "critical"],
            format_func=lambda s: f"{_SEVERITY_ICONS.get(s, '')} {s.capitalize()}",
            index=["info", "warning", "critical"].index(
                existing_rule.get("severity", "info")
            ) if is_editing else 0,
            key="rule_severity",
        )

    with col2:
        scope = st.radio(
            "Apply To",
            options=["watchlist", "single"],
            format_func=lambda s: "Entire Watchlist" if s == "watchlist" else "Specific Ticker",
            horizontal=True,
            index=0 if (not is_editing or existing_rule.get("scope") == "watchlist") else 1,
            key="rule_scope",
        )

    rule_ticker = None
    if scope == "single":
        rule_ticker = st.text_input(
            "Ticker Symbol",
            value=existing_rule.get("ticker", "") if is_editing else "",
            placeholder="e.g., AAPL",
            max_chars=10,
            key="rule_ticker",
        ).upper()

    st.markdown("---")

    # ── Conditions Builder ──────────────────────────────────
    st.markdown(
        '<p style="color: #E6EDF3; font-weight: 600; margin-bottom: 8px;">Conditions</p>',
        unsafe_allow_html=True,
    )

    # Load existing conditions or start with one empty
    if is_editing:
        try:
            existing_conditions = json.loads(existing_rule.get("conditions", "[]"))
        except (json.JSONDecodeError, TypeError):
            existing_conditions = []
    else:
        existing_conditions = []

    # Use session state to track conditions in the form
    if "form_conditions" not in st.session_state:
        st.session_state.form_conditions = (
            existing_conditions.copy() if existing_conditions else [{"signal_id": "", "operator": "", "value": 0.0, "params": {}}]
        )
    elif is_editing and st.session_state.get("_last_edited_id") != editing_id:
        st.session_state.form_conditions = existing_conditions.copy() if existing_conditions else [{"signal_id": "", "operator": "", "value": 0.0, "params": {}}]
        st.session_state._last_edited_id = editing_id

    conditions = st.session_state.form_conditions

    categories = get_signal_categories()
    conditions_changed = False

    for i, cond in enumerate(conditions):
        with st.container():
            st.markdown(
                f'<p style="color: #8B949E; font-size: 0.75rem; margin-bottom: 2px;">Condition {i + 1}</p>',
                unsafe_allow_html=True,
            )

            c1, c2, c3, c4, c5 = st.columns([2, 2, 1.5, 1.5, 0.5])

            # Determine current selections
            current_signal_id = cond.get("signal_id", "")
            current_signal_def = SIGNAL_CATALOG.get(current_signal_id, {})
            current_category = current_signal_def.get("category", categories[0] if categories else "")

            with c1:
                # Category selector
                cat_index = categories.index(current_category) if current_category in categories else 0
                new_category = st.selectbox(
                    "Category",
                    options=categories,
                    index=cat_index,
                    key=f"cat_{i}",
                    label_visibility="collapsed",
                )
                if new_category != current_category:
                    cond["signal_id"] = ""
                    cond["operator"] = ""
                    cond["params"] = {}
                    conditions_changed = True
                    current_category = new_category

            # Get signals for current category
            signals = get_signals_by_category(current_category)
            signal_options = {s["signal_id"]: s["name"] for s in signals}

            with c2:
                # Signal selector
                signal_ids = list(signal_options.keys())
                sig_index = signal_ids.index(current_signal_id) if current_signal_id in signal_ids else 0
                new_signal_id = st.selectbox(
                    "Signal",
                    options=signal_ids,
                    index=sig_index,
                    format_func=lambda sid: signal_options.get(sid, sid),
                    key=f"sig_{i}",
                    label_visibility="collapsed",
                )
                if new_signal_id != current_signal_id:
                    cond["signal_id"] = new_signal_id
                    cond["operator"] = ""
                    cond["params"] = {}
                    conditions_changed = True
                    current_signal_id = new_signal_id

            # Get operators for current signal
            signal_def = SIGNAL_CATALOG.get(current_signal_id, {})
            operators = signal_def.get("operators", [">", "<", ">=", "<="])

            _OP_LABELS = {
                ">": "> (above)", "<": "< (below)", ">=": "≥ (at least)", "<=": "≤ (at most)",
                "==": "= (equals)", "crosses_above": "↑ crossed above", "crosses_below": "↓ crossed below",
                "touches_upper": "▲ touched upper band", "touches_lower": "▼ touched lower band",
            }

            with c3:
                op_index = operators.index(cond.get("operator", operators[0])) if cond.get("operator") in operators else 0
                new_operator = st.selectbox(
                    "Operator",
                    options=operators,
                    index=op_index,
                    format_func=lambda o: _OP_LABELS.get(o, o),
                    key=f"op_{i}",
                    label_visibility="collapsed",
                )
                if new_operator != cond.get("operator"):
                    cond["operator"] = new_operator
                    conditions_changed = True

            with c4:
                unit = signal_def.get("unit", "")
                unit_display = f" ({unit})" if unit else ""
                new_value = st.number_input(
                    f"Value{unit_display}",
                    value=float(cond.get("value", 0.0)),
                    step=1.0 if unit in ("pts", "flags", "") else 0.5,
                    key=f"val_{i}",
                    label_visibility="collapsed",
                )
                if new_value != cond.get("value"):
                    cond["value"] = new_value
                    conditions_changed = True

            with c5:
                if len(conditions) > 1:
                    if st.button("✕", key=f"rm_{i}", help="Remove this condition"):
                        conditions.pop(i)
                        st.session_state.form_conditions = conditions
                        st.rerun()

            # Show signal description
            desc = signal_def.get("description", "")
            if desc:
                st.markdown(
                    f'<p style="color: #484F58; font-size: 0.7rem; margin-top: -8px; '
                    f'margin-bottom: 8px;">{desc}</p>',
                    unsafe_allow_html=True,
                )

            # Show cross operator note
            if new_operator in ("crosses_above", "crosses_below"):
                st.markdown(
                    '<p style="color: #D29922; font-size: 0.7rem; margin-top: -4px;">'
                    'ⓘ Cross detection needs a baseline — fires on the <em>next</em> check cycle.</p>',
                    unsafe_allow_html=True,
                )

            # Show params for signals that have them
            signal_params = signal_def.get("params", {})
            for param_key, param_spec in signal_params.items():
                if not isinstance(param_spec, dict):
                    continue
                param_type = param_spec.get("type", "")
                if param_type == "choice":
                    options = param_spec.get("options", [])
                    default = param_spec.get("default", options[0] if options else 0)
                    current_val = cond.get("params", {}).get(param_key, default)
                    new_param_val = st.selectbox(
                        f"{param_key.replace('_', ' ').title()}",
                        options=options,
                        index=options.index(current_val) if current_val in options else 0,
                        key=f"param_{i}_{param_key}",
                    )
                    if new_param_val != current_val:
                        if "params" not in cond:
                            cond["params"] = {}
                        cond["params"][param_key] = new_param_val
                        conditions_changed = True
                elif param_type == "int":
                    default = param_spec.get("default", 5)
                    min_v = param_spec.get("min", 1)
                    max_v = param_spec.get("max", 365)
                    current_val = cond.get("params", {}).get(param_key, default)
                    new_param_val = st.number_input(
                        f"{param_key.replace('_', ' ').title()}",
                        value=int(current_val),
                        min_value=min_v,
                        max_value=max_v,
                        key=f"param_{i}_{param_key}",
                    )
                    if new_param_val != current_val:
                        if "params" not in cond:
                            cond["params"] = {}
                        cond["params"][param_key] = int(new_param_val)
                        conditions_changed = True

    # Update session state if conditions changed
    if conditions_changed:
        st.session_state.form_conditions = conditions

    # Add condition button
    if len(conditions) < 3:
        if st.button("➕ Add Condition", use_container_width=True, key="add_cond"):
            conditions.append({"signal_id": "", "operator": "", "value": 0.0, "params": {}})
            st.session_state.form_conditions = conditions
            st.rerun()
    else:
        st.markdown(
            '<p style="color: #484F58; font-size: 0.75rem;">Maximum 3 conditions per rule.</p>',
            unsafe_allow_html=True,
        )

    # Logic operator (only when > 1 condition)
    logic_operator = "AND"
    if len(conditions) > 0:
        logic_operator = st.radio(
            "Trigger when",
            options=["AND", "OR"],
            format_func=lambda x: f"All conditions are true (AND)" if x == "AND" else f"Any condition is true (OR)",
            horizontal=True,
            index=0 if (not is_editing or existing_rule.get("logic_operator") == "AND") else 1,
            key="rule_logic",
        )

    st.markdown("---")

    # ── Save / Cancel ───────────────────────────────────────
    col_save, col_cancel = st.columns([1, 1])

    with col_save:
        if st.button("💾 Save Rule", use_container_width=True, key="save_rule"):
            # Validate
            errors = []
            if not rule_name.strip():
                errors.append("Rule name is required.")

            # Check at least one condition has a signal and operator
            valid_conditions = [
                c for c in conditions
                if c.get("signal_id") and c.get("operator")
            ]
            if not valid_conditions:
                errors.append("Add at least one condition with a signal and operator.")

            if errors:
                for err in errors:
                    st.error(err)
            else:
                conditions_json = json.dumps(valid_conditions)

                if is_editing:
                    assert editing_id is not None
                    update_custom_alert_rule(
                        editing_id,
                        name=rule_name.strip(),
                        severity=severity,
                        scope=scope,
                        ticker=rule_ticker if scope == "single" else None,
                        conditions=conditions_json,
                        logic_operator=logic_operator,
                    )
                    st.session_state.pop("editing_rule_id", None)
                    st.session_state.pop("form_conditions", None)
                    st.session_state.pop("_last_edited_id", None)
                    st.success(f"Updated '{rule_name.strip()}'")
                else:
                    _rid = create_custom_alert_rule(
                        user_id=user["id"],
                        name=rule_name.strip(),
                        scope=scope,
                        ticker=rule_ticker if scope == "single" else None,
                        conditions=conditions_json,
                        logic_operator=logic_operator,
                        severity=severity,
                    )
                    st.session_state.pop("form_conditions", None)
                    st.success(f"Created '{rule_name.strip()}'")
                st.rerun()

    with col_cancel:
        if is_editing:
            if st.button("Cancel Editing", use_container_width=True, key="cancel_edit"):
                st.session_state.pop("editing_rule_id", None)
                st.session_state.pop("form_conditions", None)
                st.session_state.pop("_last_edited_id", None)
                st.rerun()
        else:
            if st.button("Clear Form", use_container_width=True, key="clear_form"):
                st.session_state.form_conditions = [{"signal_id": "", "operator": "", "value": 0.0, "params": {}}]
                st.rerun()
