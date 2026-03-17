import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="Solo 401(k) Contribution & Compliance Assistant",
    page_icon="📘",
    layout="wide"
)

# -----------------------------
# 2026 Rules / Constants
# -----------------------------
TAX_YEAR = 2026
ELECTIVE_DEFERRAL_LIMIT = 24500
CATCH_UP_50_PLUS = 8000
CATCH_UP_60_TO_63 = 11250
ANNUAL_ADDITIONS_LIMIT = 72000
COMPENSATION_CAP = 360000
FORM_5500_EZ_THRESHOLD = 250000

# -----------------------------
# Helpers
# -----------------------------
def currency(x):
    return f"${x:,.2f}"

def percent(x):
    return f"{x:.1f}%"

def get_catch_up_limit(age: int) -> float:
    if 60 <= age <= 63:
        return CATCH_UP_60_TO_63
    if age >= 50:
        return CATCH_UP_50_PLUS
    return 0.0

def get_brackets_2026(filing_status: str):
    if filing_status == "Married Filing Jointly":
        return [
            (24800, 0.10),
            (100800, 0.12),
            (211400, 0.22),
            (403550, 0.24),
            (512450, 0.32),
            (768700, 0.35),
            (float("inf"), 0.37),
        ]
    else:  # Single
        return [
            (12400, 0.10),
            (50400, 0.12),
            (105700, 0.22),
            (201775, 0.24),
            (256225, 0.32),
            (640600, 0.35),
            (float("inf"), 0.37),
        ]

def federal_tax_2026(taxable_income: float, filing_status: str) -> float:
    income = max(0.0, taxable_income)
    brackets = get_brackets_2026(filing_status)

    tax = 0.0
    lower_bound = 0.0

    for upper_bound, rate in brackets:
        taxable_at_rate = min(income, upper_bound) - lower_bound
        if taxable_at_rate > 0:
            tax += taxable_at_rate * rate
            lower_bound = upper_bound
        else:
            break

    return tax

def federal_marginal_rate_2026(taxable_income: float, filing_status: str) -> float:
    income = max(0.0, taxable_income)
    brackets = get_brackets_2026(filing_status)

    lower_bound = 0.0
    for upper_bound, rate in brackets:
        if income <= upper_bound:
            return rate * 100
        lower_bound = upper_bound

    return 37.0

def entity_compensation_label(entity_type: str) -> str:
    if entity_type in ["S Corporation", "C Corporation"]:
        return "W-2 compensation from the business ($)"
    if entity_type == "Partnership / LLC taxed as Partnership":
        return "Partner earned income used for plan calculations ($)"
    return "Net earnings used for plan calculations ($)"

def employer_contribution_rate_label(entity_type: str) -> str:
    if entity_type in ["S Corporation", "C Corporation"]:
        return "25% of eligible compensation"
    return "20% simplified self-employed approximation"

def calculate_employer_contribution_max(entity_type: str, compensation: float, available_base_deferral: float) -> float:
    eligible_comp = min(max(0.0, compensation), COMPENSATION_CAP)

    if entity_type in ["S Corporation", "C Corporation"]:
        raw_employer = eligible_comp * 0.25
    else:
        # Simplified self-employed approximation for MVP
        raw_employer = eligible_comp * 0.20

    cap_after_employee = max(0.0, ANNUAL_ADDITIONS_LIMIT - available_base_deferral)
    return max(0.0, min(raw_employer, cap_after_employee))

# -----------------------------
# Styling
# -----------------------------
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1320px;
    }

    .hero-box {
        padding: 1.35rem 1.5rem;
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(59,130,246,0.10), rgba(16,185,129,0.08));
        margin-bottom: 1rem;
    }

    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 0.4rem;
    }

    .hero-subtitle {
        font-size: 1rem;
        opacity: 0.92;
        margin-bottom: 0;
    }

    .section-title {
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
    }

    .box {
        padding: 1rem 1.1rem;
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 16px;
        background: rgba(127,127,127,0.06);
    }

    .note-box {
        padding: 0.95rem 1.05rem;
        border-left: 4px solid #22c55e;
        border-radius: 12px;
        background: rgba(34,197,94,0.08);
        margin-top: 0.75rem;
    }

    .warn-box {
        padding: 0.95rem 1.05rem;
        border-left: 4px solid #f59e0b;
        border-radius: 12px;
        background: rgba(245,158,11,0.10);
        margin-top: 0.75rem;
    }

    .disclaimer-box {
        padding: 1rem 1.1rem;
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 14px;
        background: rgba(127,127,127,0.05);
        font-size: 0.95rem;
        opacity: 0.95;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Sidebar Inputs
# -----------------------------
st.sidebar.header("Solo 401(k) Planning Inputs")
st.sidebar.caption("Version 1 MVP • 2026 rules • Pretax contribution estimate")

tax_year = st.sidebar.selectbox("Tax year", [2026], index=0)

owner_age = st.sidebar.number_input(
    "Owner age",
    min_value=18,
    max_value=100,
    value=45,
    step=1,
    format="%d"
)

filing_status = st.sidebar.selectbox(
    "Filing status",
    ["Single", "Married Filing Jointly"]
)

entity_type = st.sidebar.selectbox(
    "Entity type",
    [
        "Sole Proprietor / Single-Member LLC",
        "Partnership / LLC taxed as Partnership",
        "S Corporation",
        "C Corporation",
    ]
)

comp_label = entity_compensation_label(entity_type)
compensation = st.sidebar.number_input(
    comp_label,
    min_value=0.0,
    value=100000.0,
    step=1000.0,
    format="%.0f"
)

current_taxable_income = st.sidebar.number_input(
    "Projected taxable income before Solo 401(k) contribution ($)",
    min_value=0.0,
    value=120000.0,
    step=1000.0,
    format="%.0f"
)

other_plan_deferrals = st.sidebar.number_input(
    "Employee deferrals already used in other plans this year ($)",
    min_value=0.0,
    value=0.0,
    step=500.0,
    format="%.0f"
)

other_plan_catch_up = st.sidebar.number_input(
    "Catch-up contributions already used in other plans this year ($)",
    min_value=0.0,
    value=0.0,
    step=500.0,
    format="%.0f"
)

state_tax_rate = st.sidebar.slider(
    "Estimated state tax rate (%)",
    min_value=0.0,
    max_value=15.0,
    value=5.0,
    step=0.5
)

plan_assets = st.sidebar.number_input(
    "Estimated year-end Solo 401(k) plan assets ($)",
    min_value=0.0,
    value=0.0,
    step=5000.0,
    format="%.0f"
)

has_non_owner_employees = st.sidebar.selectbox(
    "Any non-owner employees?",
    ["No", "Yes"]
)

spouse_participating = st.sidebar.selectbox(
    "Will spouse participate in the plan?",
    ["No", "Yes"]
)

# -----------------------------
# Calculations
# -----------------------------
catch_up_limit = get_catch_up_limit(owner_age)
available_base_deferral = max(0.0, ELECTIVE_DEFERRAL_LIMIT - other_plan_deferrals)
available_catch_up = max(0.0, catch_up_limit - other_plan_catch_up)

employer_contribution_max = calculate_employer_contribution_max(
    entity_type=entity_type,
    compensation=compensation,
    available_base_deferral=available_base_deferral
)

non_catchup_total = min(
    ANNUAL_ADDITIONS_LIMIT,
    available_base_deferral + employer_contribution_max
)

# Recompute employer contribution after annual additions cap
employer_contribution_max = max(0.0, non_catchup_total - available_base_deferral)

max_total_contribution = non_catchup_total + available_catch_up

federal_marginal_rate = federal_marginal_rate_2026(current_taxable_income, filing_status)
taxable_income_after_contribution = max(0.0, current_taxable_income - max_total_contribution)

federal_tax_before = federal_tax_2026(current_taxable_income, filing_status)
federal_tax_after = federal_tax_2026(taxable_income_after_contribution, filing_status)
estimated_federal_tax_savings = max(0.0, federal_tax_before - federal_tax_after)

estimated_state_tax_savings = max_total_contribution * (state_tax_rate / 100)
estimated_total_tax_savings = estimated_federal_tax_savings + estimated_state_tax_savings

# Eligibility / compliance
appears_solo_eligible = has_non_owner_employees == "No"
form_5500_ez_flag = plan_assets > FORM_5500_EZ_THRESHOLD

compliance_flags = []

if appears_solo_eligible:
    eligibility_status = "Appears eligible as Solo 401(k)"
else:
    eligibility_status = "Needs review — non-owner employees may make this more than a Solo 401(k)"

if has_non_owner_employees == "Yes":
    compliance_flags.append(
        "Non-owner employees are present. This may disqualify the arrangement from being treated as a one-participant plan."
    )

if form_5500_ez_flag:
    compliance_flags.append(
        "Estimated year-end assets exceed $250,000. Form 5500-EZ may be required."
    )

if spouse_participating == "Yes":
    compliance_flags.append(
        "Spouse participation is allowed in a one-participant plan if the spouse works in the business. Current calculations shown here are owner-only."
    )

if entity_type == "S Corporation":
    compliance_flags.append(
        "S corporation contributions should be based on W-2 compensation, not shareholder distributions."
    )

if entity_type in ["Sole Proprietor / Single-Member LLC", "Partnership / LLC taxed as Partnership"]:
    compliance_flags.append(
        "Self-employed employer contribution shown here is a simplified approximation and should be validated with Publication 560 worksheets."
    )

if other_plan_deferrals >= ELECTIVE_DEFERRAL_LIMIT:
    compliance_flags.append(
        "The annual elective deferral limit appears fully used in other plans. Only employer contribution and any remaining catch-up may still be available."
    )

# -----------------------------
# Header
# -----------------------------
st.markdown("""
<div class="hero-box">
    <div class="hero-title">Solo 401(k) Contribution & Compliance Assistant</div>
    <p class="hero-subtitle">
        Estimate eligibility, contribution limits, current-year tax benefit, and compliance flags
        for a one-participant 401(k) planning conversation.
    </p>
</div>
""", unsafe_allow_html=True)

st.caption("Internal demo • Version 1 MVP • 2026 rules • Pretax estimate")

# -----------------------------
# KPI Row
# -----------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Eligibility Status", "Eligible" if appears_solo_eligible else "Needs Review")
k2.metric("Max Total Contribution", currency(max_total_contribution))
k3.metric("Estimated Tax Benefit", currency(estimated_total_tax_savings))
k4.metric("Federal Marginal Rate", percent(federal_marginal_rate))

st.divider()

# -----------------------------
# Main Layout
# -----------------------------
left, right = st.columns([1.35, 1])

with left:
    st.markdown('<div class="section-title">Contribution Breakdown</div>', unsafe_allow_html=True)

    breakdown_df = pd.DataFrame({
        "Category": [
            "Available employee deferral",
            "Available catch-up",
            "Estimated employer contribution max",
            "Estimated maximum total contribution",
            "Projected taxable income after contribution"
        ],
        "Value": [
            available_base_deferral,
            available_catch_up,
            employer_contribution_max,
            max_total_contribution,
            taxable_income_after_contribution
        ]
    })

    display_breakdown = breakdown_df.copy()
    display_breakdown["Value"] = display_breakdown["Value"].map(currency)

    st.dataframe(display_breakdown, hide_index=True, use_container_width=True)

    st.markdown(
        f"""
        <div class="note-box">
            <strong>Quick read:</strong><br>
            Based on the inputs entered, the owner appears to have an estimated maximum Solo 401(k)
            contribution of <strong>{currency(max_total_contribution)}</strong>. At current assumptions,
            that may reduce current-year taxes by approximately <strong>{currency(estimated_total_tax_savings)}</strong>.
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="section-title" style="margin-top:1rem;">Estimated Tax Benefit</div>', unsafe_allow_html=True)

    tax_df = pd.DataFrame({
        "Measure": [
            "Federal tax before contribution",
            "Federal tax after contribution",
            "Estimated federal tax savings",
            "Estimated state tax savings",
            "Estimated total tax savings"
        ],
        "Value": [
            federal_tax_before,
            federal_tax_after,
            estimated_federal_tax_savings,
            estimated_state_tax_savings,
            estimated_total_tax_savings
        ]
    })

    display_tax = tax_df.copy()
    display_tax["Value"] = display_tax["Value"].map(currency)
    st.dataframe(display_tax, hide_index=True, use_container_width=True)

with right:
    st.markdown('<div class="section-title">Key Assumptions</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="box">
            <p><strong>Tax year:</strong> {tax_year}</p>
            <p><strong>Owner age:</strong> {owner_age}</p>
            <p><strong>Filing status:</strong> {filing_status}</p>
            <p><strong>Entity type:</strong> {entity_type}</p>
            <p><strong>Compensation used:</strong> {currency(compensation)}</p>
            <p><strong>Taxable income before contribution:</strong> {currency(current_taxable_income)}</p>
            <p><strong>Other plan deferrals used:</strong> {currency(other_plan_deferrals)}</p>
            <p><strong>Other plan catch-up used:</strong> {currency(other_plan_catch_up)}</p>
            <p><strong>State tax rate:</strong> {percent(state_tax_rate)}</p>
            <p><strong>Estimated year-end plan assets:</strong> {currency(plan_assets)}</p>
            <p><strong>Employer contribution formula:</strong> {employer_contribution_rate_label(entity_type)}</p>
            <p style="margin-bottom:0;"><strong>Spouse participating:</strong> {spouse_participating}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="section-title" style="margin-top:1rem;">Compliance Flags</div>', unsafe_allow_html=True)

    if compliance_flags:
        for flag in compliance_flags:
            st.warning(flag)
    else:
        st.success("No major compliance warning triggered by the current inputs.")

# -----------------------------
# Charts
# -----------------------------
st.divider()
c1, c2 = st.columns(2)

with c1:
    st.markdown('<div class="section-title">Contribution Mix</div>', unsafe_allow_html=True)
    fig_contrib = go.Figure()
    fig_contrib.add_bar(
        x=["Employee Deferral", "Catch-Up", "Employer Contribution"],
        y=[available_base_deferral, available_catch_up, employer_contribution_max]
    )
    fig_contrib.update_layout(
        xaxis_title="Contribution Type",
        yaxis_title="Amount ($)",
        height=420,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig_contrib, use_container_width=True)

with c2:
    st.markdown('<div class="section-title">Tax Benefit View</div>', unsafe_allow_html=True)
    fig_tax = go.Figure()
    fig_tax.add_bar(
        x=["Federal Savings", "State Savings", "Total Savings"],
        y=[estimated_federal_tax_savings, estimated_state_tax_savings, estimated_total_tax_savings]
    )
    fig_tax.update_layout(
        xaxis_title="Tax Measure",
        yaxis_title="Amount ($)",
        height=420,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    st.plotly_chart(fig_tax, use_container_width=True)

# -----------------------------
# Planning Summary
# -----------------------------
st.divider()
st.markdown('<div class="section-title">Planning Summary</div>', unsafe_allow_html=True)

p1, p2, p3 = st.columns(3)

with p1:
    st.info(
        f"**Eligibility:** {eligibility_status}\n\n"
        f"This is a screening result based on whether non-owner employees are present."
    )

with p2:
    st.info(
        f"**Estimated maximum contribution:** {currency(max_total_contribution)}\n\n"
        f"This combines available employee deferral, catch-up if applicable, and estimated employer contribution."
    )

with p3:
    st.info(
        f"**Estimated current-year tax benefit:** {currency(estimated_total_tax_savings)}\n\n"
        f"This assumes pretax contributions and uses 2026 federal brackets plus the state tax rate entered."
    )

# -----------------------------
# Disclaimer
# -----------------------------
st.markdown("""
<div class="disclaimer-box">
    <strong>Important disclaimer:</strong> This is a simplified educational and administrative support tool,
    not legal, ERISA, payroll, or tax filing advice. Self-employed contribution calculations may require
    a more precise worksheet approach. This version assumes pretax contribution modeling only and is intended
    for screening, planning conversations, and next-step triage.
</div>
""", unsafe_allow_html=True)
