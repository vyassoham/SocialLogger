"""
SocialLogger SMM SaaS App

Streamlit web application providing a high-fidelity glassmorphic dashboard
to create, schedule, log, and analyze social media posts using Gemini AI.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import time
import os

from database.manager import DatabaseManager
from database.models import SocialAccount, Post
from services.ai_assistant import AIAssistant
from services.scheduler import PostScheduler
from utils.analytics import AnalyticsCompiler

# =====================================================================
# Page Configurations & Styling
# =====================================================================
st.set_page_config(
    page_title="SocialLogger – AI Social Manager",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Glassmorphism CSS Injector
st.markdown("""
<style>
    /* Dark glassmorphic background & main settings */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #f8fafc;
    }
    
    /* Header styling */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 700 !important;
        color: #ffffff !important;
        text-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    /* Glassmorphism card container */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .glass-card:hover {
        border-color: rgba(99, 102, 241, 0.3);
        transform: translateY(-2px);
    }
    
    /* Metrics container */
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(to right, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 4px;
    }
    
    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Tab overrides */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: rgba(255, 255, 255, 0.02);
        padding: 8px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.03);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 600;
        border: none;
        transition: all 0.2s;
        padding: 0 20px;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: rgba(255, 255, 255, 0.05);
        color: #ffffff;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #4f46e5 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(to right, #4f46e5, #7c3aed);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
        transition: all 0.2s;
    }
    
    .stButton>button:hover {
        background: linear-gradient(to right, #6366f1, #8b5cf6);
        box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
        transform: translateY(-1px);
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# State Initialization & Helper Functions
# =====================================================================
@st.cache_resource
def get_services():
    """Initializes the backend managers."""
    db = DatabaseManager()
    ai = AIAssistant()
    scheduler = PostScheduler(db)
    compiler = AnalyticsCompiler(db)
    return db, ai, scheduler, compiler

db, ai, scheduler, compiler = get_services()


def seed_demo_data():
    """Pre-populates the database with demo accounts and metrics to look visually complete."""
    accounts = db.list_social_accounts()
    if not accounts:
        # Seed Accounts
        db.save_social_account(SocialAccount(
            platform="twitter",
            handle="@vyassoham",
            credentials={"access_token": "mock_tw_token_123"},
            rate_limit_remaining=15,
            rate_limit_reset=datetime.utcnow() + timedelta(minutes=15)
        ))
        db.save_social_account(SocialAccount(
            platform="linkedin",
            handle="Soham Vyas",
            credentials={"access_token": "mock_li_token_456"},
            rate_limit_remaining=30,
            rate_limit_reset=datetime.utcnow() + timedelta(hours=1)
        ))
        db.save_social_account(SocialAccount(
            platform="instagram",
            handle="soham.codes",
            credentials={"access_token": "mock_ig_token_789"},
            rate_limit_remaining=20,
            rate_limit_reset=datetime.utcnow() + timedelta(minutes=30)
        ))
        
        # Seed Past Posts with historical metrics
        today = date.today()
        
        post1 = db.save_post(Post(
            content="Excited to share that we are developing UniSchema—a universal data validation engine using Pydantic and Pandas! Supporting Excel, PDF, JSON, and CSV files seamlessly. #DataScience #Python",
            platforms=["twitter", "linkedin"],
            status="published",
            schedule_time=datetime.utcnow() - timedelta(days=6),
            published_time=datetime.utcnow() - timedelta(days=6),
            external_ids={"twitter": "tw_demo1", "linkedin": "li_demo1"}
        ))
        compiler.populate_mock_analytics(post1.id, today - timedelta(days=6), days=7)

        post2 = db.save_post(Post(
            content="Building complex web apps requires rich, intuitive layouts. Combining Streamlit with Custom CSS creates beautiful glassmorphic structures for high-end SaaS applications.",
            media_url="https://images.unsplash.com/photo-1551288049-bebda4e38f71",
            platforms=["linkedin", "instagram"],
            status="published",
            schedule_time=datetime.utcnow() - timedelta(days=3),
            published_time=datetime.utcnow() - timedelta(days=3),
            external_ids={"linkedin": "li_demo2", "instagram": "ig_demo2"}
        ))
        compiler.populate_mock_analytics(post2.id, today - timedelta(days=3), days=4)
        
        # Seed one future scheduled post
        db.save_post(Post(
            content="Automating data pipelines saves hours of manual checking. Find out how to write custom schema definitions with UniSchema tomorrow!",
            platforms=["twitter"],
            status="scheduled",
            schedule_time=datetime.utcnow() + timedelta(hours=4)
        ))
        
        # Seed Audit Logs
        db.log_event("SYSTEM_BOOT", "SocialLogger application initialized.", "info")
        db.log_event("ACCOUNT_CONNECTED", "Connected mock accounts: Twitter, LinkedIn, Instagram.", "info")
        db.log_event("POST_PUBLISHED", "Published historical post campaign 'UniSchema Development'", "info", {"post_id": post1.id})
        db.log_event("POST_PUBLISHED", "Published historical post campaign 'Streamlit Layouts'", "info", {"post_id": post2.id})

# Run demo seeding
seed_demo_data()

# Process Queue automatically on load/refresh
processed_count = scheduler.process_pending_queue()
if processed_count > 0:
    st.toast(f"Scheduler run complete: published {processed_count} posts!", icon="🚀")

# =====================================================================
# Sidebar Layout
# =====================================================================
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>🎯 SocialLogger</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 0.9rem;'>AI-Powered Social Media Management</p>", unsafe_allow_html=True)
    st.write("---")
    
    # System Status Panel
    st.markdown("### System Health")
    st.success("Scheduler: Active")
    st.success("Database: Connected")
    
    if ai.is_mock:
        st.info("AI Mode: Mock Engine")
    else:
        st.success("AI Mode: Gemini Active")

    st.write("---")
    
    # Force run scheduler button
    if st.button("Trigger Queue Check", use_container_width=True):
        runs = scheduler.process_pending_queue()
        if runs > 0:
            st.success(f"Published {runs} pending posts!")
            time.sleep(1)
            st.rerun()
        else:
            st.info("No posts pending in scheduling queue.")

# =====================================================================
# Dashboard Header
# =====================================================================
st.title("Social Media Management Hub")
st.markdown("Automate campaigns, generate content using Gemini AI, and track cross-platform metrics.")

# Tabs configuration
tab_overview, tab_creator, tab_queue, tab_channels, tab_audits = st.tabs([
    "📊 Analytics Overview",
    "✨ AI Creator Studio",
    "📅 Scheduled Queue",
    "🔌 Connected Channels",
    "📜 System Audit Log"
])

# =====================================================================
# Tab 1: Overview Dashboard
# =====================================================================
with tab_overview:
    # 1. Metric Cards
    accounts = db.list_social_accounts()
    posts = db.list_posts()
    published_posts = [p for p in posts if p.status == "published"]
    scheduled_posts = [p for p in posts if p.status == "scheduled"]
    
    # Compile totals
    tot_impressions = 0
    tot_engagements = 0
    for p in published_posts:
        rep = compiler.compile_post_report(p)
        tot_impressions += rep["impressions"]
        tot_engagements += rep["engagements"]
        
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-label">Total Reach</div>
            <div class="metric-value">{tot_impressions:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-label">Total Engagements</div>
            <div class="metric-value">{tot_engagements:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-label">Active Channels</div>
            <div class="metric-value">{len(accounts)}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-label">Queue Size</div>
            <div class="metric-value">{len(scheduled_posts)}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. Charts Section
    st.write("### Engagement Growth Trends")
    df_history = compiler.get_historical_dataframe()
    
    if not df_history.empty:
        chart_col, pie_col = st.columns([2, 1])
        
        with chart_col:
            fig = px.line(
                df_history, 
                x="Date", 
                y=["Impressions", "Engagements"],
                title="Cross-platform Growth Trends",
                template="plotly_dark",
                color_discrete_sequence=["#818cf8", "#c084fc"]
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend_title_text="Metrics"
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with pie_col:
            # Platform comparison
            comparison = compiler.get_platform_comparison()
            pie_data = []
            for plat, data in comparison.items():
                pie_data.append({
                    "Platform": plat.capitalize(),
                    "Posts": data["posts"],
                    "Impressions": data["impressions"]
                })
            df_pie = pd.DataFrame(pie_data)
            
            fig_pie = px.pie(
                df_pie, 
                names="Platform", 
                values="Impressions",
                title="Impressions Share by Platform",
                template="plotly_dark",
                color_discrete_sequence=["#4f46e5", "#818cf8", "#c084fc"]
            )
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No publication metrics data available yet.")

    # 3. Export Reports Panel
    st.write("---")
    st.markdown("### Export Campaign Performance Data")
    exp1, exp2, _ = st.columns([1, 1, 2])
    with exp1:
        if st.button("Export to CSV", use_container_width=True):
            fpath = compiler.export_posts_summary_csv("campaign_report.csv")
            with open(fpath, "rb") as f:
                st.download_button(
                    "Download CSV Report",
                    data=f,
                    file_name="campaign_report.csv",
                    mime="text/csv",
                    use_container_width=True
                )
    with exp2:
        if st.button("Export to JSON", use_container_width=True):
            fpath = compiler.export_posts_summary_json("campaign_report.json")
            with open(fpath, "rb") as f:
                st.download_button(
                    "Download JSON Report",
                    data=f,
                    file_name="campaign_report.json",
                    mime="application/json",
                    use_container_width=True
                )

# =====================================================================
# Tab 2: AI Creator Studio
# =====================================================================
with tab_creator:
    st.write("### AI-Powered Post Generation & Optimizer")
    
    creator_col, preview_col = st.columns([3, 2])
    
    with creator_col:
        topic_input = st.text_area(
            "What is the topic or theme of your campaign?",
            placeholder="e.g., Launching our new Python validation package UniSchema..."
        )
        
        col_tone, col_plat = st.columns(2)
        with col_tone:
            tone_selection = st.selectbox(
                "Tone of voice",
                ["Witty", "Professional", "Bold", "Educational"]
            )
        with col_plat:
            platform_selection = st.selectbox(
                "Primary Platform Target",
                ["Twitter", "LinkedIn", "Instagram"]
            )

        # Generate Button
        generated_text = ""
        if st.button("Generate Post Copy"):
            if topic_input:
                with st.spinner("Gemini AI is crafting your post..."):
                    generated_text = ai.generate_post(topic_input, tone_selection, platform_selection)
                    st.session_state["draft_content"] = generated_text
            else:
                st.warning("Please provide a topic first.")
                
        # Editor Box
        draft_content = st.text_area(
            "Draft Content",
            value=st.session_state.get("draft_content", ""),
            height=200,
            key="editor_text"
        )
        
        # Optimize / Polishing actions
        st.write("### Content Polishing")
        opt_tw, opt_li, opt_ig = st.columns(3)
        with opt_tw:
            if st.button("Optimize for Twitter", use_container_width=True):
                if draft_content:
                    st.session_state["draft_content"] = ai.optimize_post(draft_content, "twitter")
                    st.rerun()
        with opt_li:
            if st.button("Optimize for LinkedIn", use_container_width=True):
                if draft_content:
                    st.session_state["draft_content"] = ai.optimize_post(draft_content, "linkedin")
                    st.rerun()
        with opt_ig:
            if st.button("Optimize for Instagram", use_container_width=True):
                if draft_content:
                    st.session_state["draft_content"] = ai.optimize_post(draft_content, "instagram")
                    st.rerun()

    with preview_col:
        st.write("### AI Quality Guard & Platform Previews")
        
        if draft_content:
            # AI Analysis Guard
            with st.spinner("Scanning copy safety..."):
                analysis = ai.analyze_post(draft_content)
                
            st.markdown(f"""
            <div class="glass-card">
                <h4>AI Audit Scan</h4>
                <p><b>Sentiment:</b> {analysis['sentiment']}</p>
                <p><b>Spam Risk:</b> {analysis['spam_risk'] * 100:.1f}%</p>
                <p><b>Policy Violation:</b> {'⚠️ Violated' if analysis['policy_violation'] else '✅ Safe'}</p>
                <p><i>{analysis['reason']}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
            # Post scheduler parameters
            st.write("### Campaign Dispatch")
            target_channels = st.multiselect(
                "Distribute to Platforms",
                ["Twitter", "LinkedIn", "Instagram"],
                default=[platform_selection]
            )
            media_input = st.text_input("Attached Image URL (Optional)", placeholder="https://...")
            
            sched_date = st.date_input("Scheduled Date", value=date.today())
            sched_time = st.time_input("Scheduled Time")
            
            if st.button("Queue Scheduled Post", use_container_width=True):
                if not target_channels:
                    st.error("Please choose at least one channel.")
                else:
                    target_dt = datetime.combine(sched_date, sched_time)
                    # Convert to utc iso-friendly
                    new_post = Post(
                        content=draft_content,
                        media_url=media_input if media_input.strip() else None,
                        platforms=[c.lower().strip() for c in target_channels],
                        status="scheduled",
                        schedule_time=target_dt
                    )
                    db.save_post(new_post)
                    db.log_event("POST_SCHEDULED", f"Queued post targeting {target_channels}.", "info", {"post_id": new_post.id})
                    st.success("Post campaign successfully added to queue!")
                    time.sleep(1)
                    st.session_state["draft_content"] = ""
                    st.rerun()

# =====================================================================
# Tab 3: Publishing Queue
# =====================================================================
with tab_queue:
    st.write("### Campaign Timelines")
    
    all_posts = db.list_posts()
    
    q_sched, q_pub, q_fail = st.tabs([
        f"📅 Scheduled Queue ({len([p for p in all_posts if p.status == 'scheduled'])})",
        f"✅ Published Archives ({len([p for p in all_posts if p.status == 'published'])})",
        f"❌ Failures & Drafts ({len([p for p in all_posts if p.status in ('failed', 'draft')])})"
    ])
    
    with q_sched:
        scheduled_items = [p for p in all_posts if p.status == "scheduled"]
        if not scheduled_items:
            st.info("No pending schedules. Use the AI Creator Studio to queue a campaign.")
        else:
            for item in scheduled_items:
                with st.container():
                    st.markdown(f"""
                    <div class="glass-card">
                        <p style="color: #94a3b8; font-size: 0.85rem;">TARGETS: <b>{", ".join(item.platforms).upper()}</b> | SCHEDULED FOR: {item.schedule_time.strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                        <p style="font-size: 1.1rem; margin-top: 5px;">{item.content}</p>
                        {f'<p style="color: #818cf8; font-size: 0.85rem;">Attached Image: {item.media_url}</p>' if item.media_url else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Quick Actions
                    act_col1, act_col2, act_col3, _ = st.columns([1, 1, 1, 4])
                    with act_col1:
                        if st.button("Publish Now", key=f"pub_now_{item.id}"):
                            item.schedule_time = datetime.utcnow()
                            db.save_post(item)
                            scheduler.process_pending_queue()
                            st.rerun()
                    with act_col2:
                        # Reschedule to tomorrow
                        if st.button("Defer 24 Hrs", key=f"defer_{item.id}"):
                            item.schedule_time = item.schedule_time + timedelta(days=1)
                            db.save_post(item)
                            st.rerun()
                    with act_col3:
                        if st.button("Delete Schedule", key=f"del_{item.id}"):
                            db.delete_post(item.id)
                            st.rerun()
                    st.write("---")

    with q_pub:
        published_items = [p for p in all_posts if p.status == "published"]
        if not published_items:
            st.info("No published posts. Successful campaigns will archive here.")
        else:
            for item in published_items:
                with st.container():
                    st.markdown(f"""
                    <div class="glass-card">
                        <p style="color: #94a3b8; font-size: 0.85rem;">CHANNELS: <b>{", ".join(item.platforms).upper()}</b> | PUBLISHED AT: {item.published_time.strftime('%Y-%m-%d %H:%M:%S') if item.published_time else 'N/A'}</p>
                        <p style="font-size: 1.1rem; margin-top: 5px;">{item.content}</p>
                        <p style="color: #c084fc; font-size: 0.85rem;">External Identifiers: {item.external_ids}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Compile report
                    report = compiler.compile_post_report(item)
                    
                    rep_col1, rep_col2, rep_col3, rep_col4, rep_col5, _ = st.columns(6)
                    rep_col1.metric("Impressions", f"{report['impressions']:,}")
                    rep_col2.metric("Likes", f"{report['likes']:,}")
                    rep_col3.metric("Shares", f"{report['shares']:,}")
                    rep_col4.metric("Comments", f"{report['comments']:,}")
                    rep_col5.metric("Engagement Rate", f"{report['engagement_rate']}%")
                    st.write("---")

    with q_fail:
        failed_items = [p for p in all_posts if p.status in ("failed", "draft")]
        if not failed_items:
            st.info("No failed campaigns.")
        else:
            for item in failed_items:
                with st.container():
                    st.markdown(f"""
                    <div class="glass-card" style="border-left: 4px solid #ef4444;">
                        <p style="color: #f87171; font-weight: bold; font-size: 0.85rem;">STATUS: {item.status.upper()} | TARGETS: {", ".join(item.platforms).upper()}</p>
                        <p style="font-size: 1.1rem; margin-top: 5px;">{item.content}</p>
                        <p style="color: #fca5a5; font-size: 0.85rem; background: rgba(239, 68, 68, 0.1); padding: 8px; border-radius: 6px; margin-top: 8px;">Error details: {item.error_message}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    act_col1, act_col2, _ = st.columns([1, 1, 5])
                    with act_col1:
                        if st.button("Retry Campaign", key=f"retry_{item.id}"):
                            item.status = "scheduled"
                            item.schedule_time = datetime.utcnow()
                            db.save_post(item)
                            scheduler.process_pending_queue()
                            st.rerun()
                    with act_col2:
                        if st.button("Delete Campaign", key=f"del_fail_{item.id}"):
                            db.delete_post(item.id)
                            st.rerun()
                    st.write("---")

# =====================================================================
# Tab 4: Connected Channels
# =====================================================================
with tab_channels:
    st.write("### Managed Channels")
    
    col_chan, col_add = st.columns([3, 2])
    
    with col_chan:
        for acc in accounts:
            with st.container():
                st.markdown(f"""
                <div class="glass-card">
                    <h3>{acc.platform.capitalize()} Account</h3>
                    <p><b>Handle:</b> {acc.handle}</p>
                    <p><b>Link Status:</b> {'🟢 Connected' if acc.status == 'active' else '🔴 Connection Lost'}</p>
                    <p><b>API Quota Remaining:</b> {acc.rate_limit_remaining} requests</p>
                    <p><b>Quota Reset:</b> {acc.rate_limit_reset.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("Disconnect Channel", key=f"dis_{acc.id}"):
                    db.delete_social_account(acc.id)
                    db.log_event("ACCOUNT_DISCONNECTED", f"Disconnected {acc.platform} channel {acc.handle}", "warning")
                    st.rerun()
                st.write("---")
                
    with col_add:
        st.markdown("""
        <div class="glass-card">
            <h4>Link New Social Channel</h4>
            <p style="color: #94a3b8; font-size: 0.9rem;">Link handles using mock credentials to verify schedulers and visual components.</p>
        </div>
        """, unsafe_allow_html=True)
        
        new_plat = st.selectbox("Platform", ["Twitter", "LinkedIn", "Instagram"])
        new_handle = st.text_input("Channel Handle / Username", placeholder="@yourhandle")
        new_tok = st.text_input("OAuth Access Token", value="mock_access_token_token", type="password")
        
        if st.button("Authenticate Channel", use_container_width=True):
            if not new_handle:
                st.error("Please enter a username handle.")
            else:
                new_acc = SocialAccount(
                    platform=new_plat.lower(),
                    handle=new_handle,
                    credentials={"access_token": new_tok},
                    rate_limit_remaining=100,
                    rate_limit_reset=datetime.utcnow() + timedelta(days=1)
                )
                db.save_social_account(new_acc)
                db.log_event("ACCOUNT_CONNECTED", f"Successfully authenticated {new_plat} handle {new_handle}.", "info")
                st.success(f"{new_plat} account successfully connected!")
                time.sleep(1)
                st.rerun()

# =====================================================================
# Tab 5: System Audit Logs
# =====================================================================
with tab_audits:
    st.write("### Live System Audits")
    
    logs = db.list_audit_logs(limit=50)
    
    if not logs:
        st.info("No system events logged.")
    else:
        log_rows = []
        for l in logs:
            log_rows.append({
                "Timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Action": l.action,
                "Level": l.severity.upper(),
                "Details": l.details,
                "Context": str(l.metadata)
            })
        df_logs = pd.DataFrame(log_rows)
        
        # Color mapping for log table
        def style_logs(val):
            if val == "ERROR":
                return "color: #f87171; font-weight: bold;"
            elif val == "WARNING":
                return "color: #fbbf24; font-weight: bold;"
            return "color: #94a3b8;"

        st.dataframe(
            df_logs,
            use_container_width=True,
            column_config={
                "Timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
                "Action": st.column_config.TextColumn("Action Event", width="medium"),
                "Level": st.column_config.TextColumn("Severity", width="small"),
                "Details": st.column_config.TextColumn("Action Details", width="large"),
                "Context": st.column_config.TextColumn("System Metadata", width="medium"),
            }
        )
