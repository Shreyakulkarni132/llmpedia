import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from typing import Dict, Tuple
import time
import re
import markdown2

import utils.app_utils as au
import utils.data_cards as dc
import utils.db.db as db
import utils.db.logging_db as logging_db


def create_sidebar(full_papers_df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    ## Filter sidebar.
    st.sidebar.markdown("# 📁 Filters")
    ## Filter by year or select all of them.
    year_cols = st.sidebar.columns((1, 2))
    _ = year_cols[0].markdown("#### Year")
    all_years = year_cols[0].checkbox("All ", value=st.session_state.all_years)
    st.session_state.all_years = all_years

    _ = year_cols[1].markdown("####")
    year = year_cols[1].slider(
        "Year",
        min_value=2016,
        max_value=2025,
        value=2025,
        step=1,
        label_visibility="collapsed",
        disabled=st.session_state.all_years,
    )

    search_term = st.sidebar.text_input("Search", "")
    search_opt_cols = st.sidebar.columns((1, 1))
    title_only = search_opt_cols[0].checkbox("`Title Only`", value=True)
    code_only = search_opt_cols[1].checkbox("`Arxiv Code`", value=False)
    categories = st.sidebar.multiselect(
        "Categories",
        list(full_papers_df["category"].unique()),
    )
    topics = st.sidebar.multiselect(
        "Topic Group",
        list(full_papers_df["topic"].unique()),
    )

    min_citations = st.sidebar.select_slider(
        "Min Citations",
        options=[0, 1, 5, 10, 100],
        value=0,
    )

    ## Sort by.
    sort_by = st.sidebar.selectbox(
        "Sort By",
        ["Published Date", "Last Updated", "Citations", "Random"],
    )

    ## Year filter.
    if not st.session_state.all_years:
        papers_df = full_papers_df[full_papers_df["published"].dt.year == int(year)]
    else:
        papers_df = full_papers_df.copy()

    ## Search terms.
    if len(search_term) > 0 and title_only:
        search_term = search_term.lower()
        papers_df = papers_df[papers_df["title"].str.lower().str.contains(search_term)]
    elif len(search_term) > 0 and code_only:
        search_term = search_term.lower()
        papers_df = papers_df[
            papers_df["arxiv_code"].str.lower().str.contains(search_term)
        ]
        st.session_state.arxiv_code = search_term
    elif len(search_term) > 0:
        search_term = search_term.lower()
        papers_df = papers_df[
            papers_df["title"].str.lower().str.contains(search_term)
            | papers_df["arxiv_code"].str.lower().str.contains(search_term)
            | papers_df["authors"].str.lower().str.contains(search_term)
            | papers_df["summary"].str.lower().str.contains(search_term)
            | papers_df["contribution_title"].str.lower().str.contains(search_term)
            | papers_df["contribution_content"].str.lower().str.contains(search_term)
            | papers_df["takeaway_title"].str.lower().str.contains(search_term)
            | papers_df["takeaway_content"].str.lower().str.contains(search_term)
        ]

    ## Categories.
    if len(categories) > 0:
        papers_df = papers_df[papers_df["category"].isin(categories)]

    # Cluster.
    if len(topics) > 0:
        papers_df = papers_df[papers_df["topic"].isin(topics)]

    ## Citations.
    papers_df = papers_df[papers_df["citation_count"] >= min_citations]

    ## Order.
    if sort_by == "Last Updated":
        papers_df = papers_df.sort_values("updated", ascending=False)
    elif sort_by == "Published Date":
        papers_df = papers_df.sort_values("published", ascending=False)
    elif sort_by == "Citations":
        papers_df = papers_df.sort_values("citation_count", ascending=False)
    elif sort_by == "Random":
        papers_df = papers_df.sample(frac=1)

    return papers_df, year


def create_paper_card(paper: Dict, mode="closed", name=""):
    """Creates card UI for paper details."""
    # Main container with padding and border
    with st.container():
        # Top section with image and metadata
        img_cols = st.columns((1, 3))
        expanded = False
        if mode == "open":
            expanded = True
        paper_code = paper["arxiv_code"]
        
        # Image column
        try:
            img_cols[0].image(
                f"https://arxiv-art.s3.us-west-2.amazonaws.com/{paper_code}.png", 
                use_container_width=True
            )
        except:
            pass

        # Metadata column
        meta_col = img_cols[1]
        
        # Title with link
        paper_title = paper["title"]
        paper_url = paper["url"]
        meta_col.markdown(
            f'<h2 style="margin-top: 0; margin-bottom: 0.5em;"><a href="{paper_url}" style="color: #FF4B4B; text-decoration: none;">{paper_title}</a></h2>',
            unsafe_allow_html=True,
        )

        # Publication date
        pub_date = pd.to_datetime(paper["published"]).strftime("%d %b %Y")
        meta_col.markdown(
            f"<p style='margin-bottom: 0.5em; color: #666;'><span style='display: inline-flex; align-items: center;'>📅 <span style='margin-left: 4px;'>{pub_date}</span></span></p>", 
            unsafe_allow_html=True
        )
        
        # Topic with enhanced styling
        if "topic" in paper and not pd.isna(paper["topic"]):
            topic = paper["topic"]
            meta_col.markdown(f"""<p style='margin-bottom: 0.5em;'>
                <span style='
                    background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.1)); 
                    padding: 4px 12px; 
                    border-radius: 12px; 
                    font-size: 0.95em;
                    color: var(--text-color, currentColor);
                '>{topic}</span></p>""", unsafe_allow_html=True)

        # Authors and citations in smaller text
        influential_citations = int(paper["influential_citation_count"])
        citation_count = int(paper["citation_count"])
        citation_text = f"{citation_count} citation{'s' if citation_count != 1 else ''}"
        if influential_citations > 0:
            citation_text += f" (⭐️ {influential_citations} influential)"
            
        meta_col.markdown(
            f"""<div style='margin: 0.5em 0;'>
            <p style='color: var(--text-color, #666); font-size: 0.9em; margin-bottom: 0.8em;'>{paper['authors']}</p>
            <div style='
                display: inline-flex; 
                align-items: center; 
                background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.1)); 
                padding: 6px 12px; 
                border-radius: 12px;
                color: var(--text-color, currentColor);
            '>
            <span style='display: flex; align-items: center;'>
            <span style='margin-right: 4px;'>📊</span>
            <span style='font-size: 0.9em;'>{citation_text}</span>
            </span></div></div>""",
            unsafe_allow_html=True
        )

        # Action buttons in a row with more spacing
        meta_col.markdown("<div style='margin: 1.5em 0;'>", unsafe_allow_html=True)
        action_btn_cols = meta_col.columns((1, 1, 1))
        
        # Report button
        report_log_space = meta_col.empty()
        report_btn = action_btn_cols[0].popover("⚠️ Report")
        if report_btn.checkbox("Report bad image", key=f"report_v1_{paper_code}_{name}"):
            logging_db.report_issue(paper_code, "bad_image")
            report_log_space.success("Reported bad image. Thanks!")
            time.sleep(3)
            report_log_space.empty()
        if report_btn.checkbox("Report bad summary", key=f"report_v2_{paper_code}_{name}"):
            logging_db.report_issue(paper_code, "bad_summary")
            report_log_space.success("Reported bad summary. Thanks!")
            time.sleep(3)
            report_log_space.empty()
        if report_btn.checkbox("Report non-LLM paper", key=f"report_v3_{paper_code}_{name}"):
            logging_db.report_issue(paper_code, "non_llm")
            report_log_space.success("Reported non-LLM paper. Thanks!")
            time.sleep(3)
            report_log_space.empty()
        if report_btn.checkbox("Report bad data card", key=f"report_v4_{paper_code}_{name}"):
            logging_db.report_issue(paper_code, "bad_datacard")
            report_log_space.success("Reported bad data-card. Thanks!")
            time.sleep(3)
            report_log_space.empty()

        # # Data card button
        # datacard_btn = action_btn_cols[1].button("📊 Data Card", key=f"dashboard_{paper_code}", type="primary")
        # if datacard_btn:
        #     with st.spinner("*Loading data card...*"):
        #         db.log_visit(f"data_card_{paper_code}")
        #         html_card = dc.generate_data_card_html(paper_code)
        #         if html_card:
        #             @st.dialog(paper_title, width="large")
        #             def render():
        #                 components.html(html_card, height=700, scrolling=True)
        #             render()
        #         else:
        #             error_container = st.empty()
        #             error_container.error("Data card not available yet. Check back soon!")
        #             time.sleep(2)
        #             error_container.empty()

    # Content sections using tabs
    tab_names = [
        "❗️ Takeaways",     # Start with the most concise overview
        "📝 Research Notes",  # More detailed analysis
        "📖 Full Paper",     # Complete in-depth content
    ]
    
    # More robust repo check
    has_repos = False
    try:
        if paper_code in st.session_state["repos"].index:
            paper_repos = st.session_state["repos"].loc[paper_code]
            if isinstance(paper_repos, pd.Series):
                has_repos = True
            elif isinstance(paper_repos, pd.DataFrame) and len(paper_repos) > 0:
                has_repos = True
    except Exception as e:
        st.error(f"Error checking repos: {e}")
        
    if has_repos:
        tab_names.append("💻 Code")
        
    tab_names.extend([
        "💬 Chat",
        "🔍 Similar Papers",
    ])
    
    # Only add Insight tab if we have an insight
    if "tweet_insight" in paper and not pd.isna(paper["tweet_insight"]):
        tab_names.append("🤖 Maestro's Insight")
    tabs = st.tabs(tab_names)
    
    with tabs[0]:
        st.markdown("### ❗️ Takeaways")
        bullet_summary = (
            paper["bullet_list_summary"]
            if not pd.isna(paper["bullet_list_summary"])
            else "Not available yet, check back soon!"
        )
        bullet_summary_lines = bullet_summary.split('\n')
        numbered_summary = []
        number = 1
        
        # Regex pattern for matching emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251" 
            "]+",
            flags=re.UNICODE
        )
        
        for line in bullet_summary_lines:
            if line.strip().startswith('- '):
                # Remove the bullet point and clean the line
                clean_line = line.strip()[2:].strip()
                # Remove all emojis and extra spaces
                clean_line = emoji_pattern.sub('', clean_line).strip()
                numbered_summary.append(f"{number}. {clean_line}")
                number += 1
            else:
                # For non-bullet point lines, still remove emojis
                clean_line = emoji_pattern.sub('', line).strip()
                if clean_line:  # Only add non-empty lines
                    numbered_summary.append(clean_line)
                    
        st.markdown('\n'.join(numbered_summary))
            
    with tabs[1]:  # Research Notes
        st.markdown("### 📝 Research Notes")
        level_select = st.selectbox(
            "Detail",
            [
                "📝 High-Level Overview",
                "🔎 Detailed Research Notes",
            ],
            label_visibility="collapsed",
            index=0,
            key=f"level_select_{paper_code}{name}",
        )

        summary = (
            paper["recursive_summary"]
            if not pd.isna(paper["recursive_summary"])
            else paper["contribution_content"]
        )
        markdown_summary = paper["markdown_notes"]

        if level_select == "📝 High-Level Overview":
            st.markdown(summary)

        elif level_select == "🔎 Detailed Research Notes":
            # Add level selector with predefined values
            level_select = st.select_slider(
                "Summary Level",
                options=["Most Detailed", "Detailed", "Concise", "Very Concise"],
                value="Detailed",
                help="Adjust the level of detail in the research notes"
            )
            
            # Map selection to level values (level 1 is most detailed)
            level_map = {
                "Most Detailed": 5,  # First summary iteration (most detailed)
                "Detailed": 3,       # Second iteration
                "Concise": 2,        # Third iteration
                "Very Concise": 1    # Fourth iteration (most concise)
            }
            
            # Get notes based on selected level
            try:
                selected_level = level_map[level_select]
                detailed_notes = db.get_extended_notes(paper["arxiv_code"], level=selected_level)
                
                if detailed_notes is None:
                    # If we're trying to get more detailed notes (lower level numbers)
                    if level_map[level_select] <= 2:
                        st.warning("No more detailed notes available for this paper")
                    # If we're trying to get more concise notes (higher level numbers)
                    else:
                        st.warning("No more concise notes available for this paper")
                elif pd.isna(detailed_notes):
                    st.warning("Notes currently unavailable at this level")
                else:
                    detailed_notes = detailed_notes.replace("#", "###")
                    detailed_notes = detailed_notes.replace("<summary>", "")
                    detailed_notes = detailed_notes.replace("</summary>", "")
                    # Add word count indicator
                    word_count = len(detailed_notes.split())
                    st.caption(f"📝 {word_count:,} words")
                    st.markdown(detailed_notes)
            except Exception as e:
                st.error(f"Error retrieving notes: {str(e)}")

        # Add Application Ideas section
        st.markdown("---")
        st.markdown("### 💡 Application Ideas")
        if not pd.isna(paper["takeaway_title"]):
            st.markdown(f"#### {paper['takeaway_title']}")
        st.markdown(paper["takeaway_example"])
            
    with tabs[2]:  # Full Paper Content
        # Fetch paper content
        markdown_content, success = au.get_paper_markdown(paper_code)
        
        if success:
            # Create columns to center the content with some margin
            _, col, _ = st.columns([1, 8, 1])
            
            with col:
                # Convert markdown to HTML
                try:
                    html_content = markdown2.markdown(
                        markdown_content,
                        extras=[
                            'fenced-code-blocks',
                            'tables',
                            'header-ids',
                            'break-on-newline',
                            'latex',  # Add support for LaTeX conversion
                            'math',   # Additional math support
                        ]
                    )
                except Exception as e:
                    st.warning(f"⚠️ LaTeX rendering failed. Falling back to plain text. Error: {str(e)}")
                    # Fallback to basic conversion without LaTeX support
                    html_content = markdown2.markdown(
                        markdown_content,
                        extras=[
                            'fenced-code-blocks',
                            'tables',
                            'header-ids',
                            'break-on-newline',
                        ]
                    )
                
                # Create an HTML string with styling
                full_html = f"""
                    <html>
                        <head>
                            <link href="https://cdn.jsdelivr.net/npm/github-markdown-css/github-markdown.min.css" rel="stylesheet">
                            <style>
                                .markdown-body {{
                                    box-sizing: border-box;
                                    min-width: 200px;
                                    max-width: 100%;
                                    margin: 0 auto;
                                    padding: 1rem;
                                }}
                                body {{
                                    font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji";
                                }}
                                img {{
                                    max-width: 100%;
                                    height: auto;
                                    display: block;
                                    margin: 1.5rem auto;
                                    border-radius: 4px;
                                }}
                                pre {{
                                    background-color: #f6f8fa;
                                    border-radius: 6px;
                                    padding: 16px;
                                    overflow: auto;
                                }}
                                code {{
                                    background-color: rgba(175,184,193,0.2);
                                    padding: .2em .4em;
                                    border-radius: 6px;
                                }}
                                pre code {{
                                    background-color: transparent;
                                    padding: 0;
                                }}
                            </style>
                        </head>
                        <body class="markdown-body">
                            {html_content}
                        </body>
                    </html>
                """
                
                # Use the components.html to create a scrollable iframe
                components.html(
                    full_html,
                    height=800,
                    scrolling=True
                )
        else:
            st.warning(markdown_content)
            
    # Code & Resources tab (shown if repos exist)
    tab_index = 3
    if has_repos:
        with tabs[tab_index]:
            paper_repos = st.session_state["repos"].loc[paper_code]
            if isinstance(paper_repos, pd.Series):
                paper_repos = pd.DataFrame([paper_repos])
            
            # Convert to list of dictionaries for easier iteration
            repos_list = paper_repos.to_dict('records')
            for idx, repo in enumerate(repos_list):
                st.markdown(f"### {repo['repo_title']}")
                st.markdown(f"🔗 **Repository:** [{repo['repo_url']}]({repo['repo_url']})")
                st.markdown(f"📝 **Description:** {repo['repo_description']}")
                # Only add separator if it's not the last repo
                if idx < len(repos_list) - 1:
                    st.markdown("---")
        tab_index += 1
            
    with tabs[tab_index]:  # Chat
        paper_question = st.text_area(
            "Ask GPT Maestro about this paper.",
            height=100,
            key=f"chat_{paper_code}{name}",
        )
        if st.button("Send", key=f"send_{paper_code}{name}"):
            response = au.interrogate_paper(
                paper_question, paper_code, model="claude-3-5-sonnet-20241022"
            )
            logging_db.log_qna_db(f"[{paper_code}] ::: {paper_question}", response)
            st.chat_message("assistant").write(response)
            
    with tabs[tab_index + 1]:  # Similar Papers
        papers_df = st.session_state["papers"]
        if paper_code in papers_df.index:
            similar_codes = pd.Series(papers_df.loc[paper_code]["similar_docs"])
            if pd.isna(similar_codes).any():
                st.write("Not available yet. Check back soon!")
            else:
                similar_codes = [d for d in similar_codes if d in papers_df.index]
                if len(similar_codes) > 5:
                    similar_codes = np.random.choice(similar_codes, 5, replace=False)
                similar_df = papers_df.loc[similar_codes]
                generate_grid_gallery(similar_df, extra_key="_sim", n_cols=5)

    # GPT Maestro Insight tab (only shown if insight exists)
    if "tweet_insight" in paper and not pd.isna(paper["tweet_insight"]):
        with tabs[tab_index + 2]:
            st.markdown("### 🤖 GPT Maestro's Key Insight")
            st.markdown(f"{paper['tweet_insight']}")

    st.markdown("---")


def generate_grid_gallery(df, n_cols=5, extra_key=""):
    """Create streamlit grid gallery of paper cards with thumbnail."""
    n_rows = int(np.ceil(len(df) / n_cols))
    for i in range(n_rows):
        cols = st.columns(n_cols)
        for j in range(n_cols):
            if i * n_cols + j < len(df):
                with cols[j]:
                    try:
                        st.image(
                            f"https://arxiv-art.s3.us-west-2.amazonaws.com/{df.iloc[i*n_cols+j]['arxiv_code']}.png"
                        )
                    except:
                        pass
                    paper_url = df.iloc[i * n_cols + j]["url"]
                    paper_title = df.iloc[i * n_cols + j]["title"].replace("\n", "")
                    star_count = (
                        df.iloc[i * n_cols + j]["influential_citation_count"] > 0
                    )
                    publish_date = pd.to_datetime(
                        df.iloc[i * n_cols + j]["published"]
                    ).strftime("%b %d, %Y")
                    star = ""
                    if star_count:
                        star = "⭐️"

                    centered_code = f"""
                    <div class="centered">
                        <code>{star} {publish_date}</code>
                    </div>
                    """
                    st.markdown(centered_code, unsafe_allow_html=True)

                    paper_code = df.iloc[i * n_cols + j]["arxiv_code"]
                    punchline = df.iloc[i * n_cols + j].get("punchline")
                    focus_btn = st.button(
                        "Read More",
                        key=f"focus_{paper_code}{extra_key}",
                        help=punchline if type(punchline) == str else None,
                        use_container_width=True,
                    )
                    if focus_btn:
                        st.session_state.arxiv_code = paper_code
                        click_tab(3)

                    st.markdown(
                        f'<p style="text-align: center"><strong><a href="{paper_url}" style="color: #FF4B4B;">{paper_title}</a></strong></p>',
                        unsafe_allow_html=True,
                    )

                    last_updated = pd.to_datetime(
                        df.iloc[i * n_cols + j]["published"]
                    ).strftime("%b %d, %Y")
                    authors_str = df.iloc[i * n_cols + j]["authors"]
                    authors_str = (
                        authors_str[:30] + "..."
                        if len(authors_str) > 30
                        else authors_str
                    )
                    # st.markdown(authors_str)


def generate_citations_list(df: pd.DataFrame) -> None:
    """Generate a formatted list of paper citations with rich styling."""
    for _, paper in df.iterrows():
        # Extract paper information
        title = paper["title"].replace("\n", "")
        authors = paper["authors"]
        paper_url = paper["url"]
        paper_code = paper["arxiv_code"]
        publish_date = pd.to_datetime(paper["published"]).strftime("%b %d, %Y")
        citation_count = int(paper.get("citation_count", 0))
        influential_count = int(paper.get("influential_citation_count", 0))
        punchline = paper.get("punchline", "")

        # Build HTML components separately
        star_badge = " ⭐️" if influential_count > 0 else ""
        citation_text = f"citation{'s' if citation_count != 1 else ''}"
        punchline_div = f'<div style="margin-top: 12px; font-style: italic; color: var(--text-color, #666);">{punchline}</div>' if punchline else ''
        
        citation_html = f'''
        <div style="margin: 20px 0; padding: 20px; border-radius: 8px; border-left: 4px solid var(--arxiv-red);">
            <div style="margin-bottom: 12px;">
                <span onclick="parent.postMessage({{cmd: 'streamlit:setComponentValue', args: {{value: '{paper_code}', dataType: 'str', key: 'arxiv_code'}}}}, '*')" style="color: var(--arxiv-red); text-decoration: none; font-size: 1.1em; font-weight: bold; cursor: pointer;">{title}</span>{star_badge}
            </div>
            <div style="color: var(--text-color, #666); font-size: 0.9em; margin-bottom: 8px;">
                {authors}
            </div>
            <div style="display: flex; gap: 12px; margin-top: 8px; font-size: 0.9em;">
                <span style="background-color: rgba(179, 27, 27, 0.05); padding: 4px 8px; border-radius: 4px;">📅 {publish_date}</span>
                <span style="background-color: rgba(179, 27, 27, 0.05); padding: 4px 8px; border-radius: 4px;">📊 {citation_count} {citation_text}</span>
                <a href="{paper_url}" target="_blank" style="text-decoration: none;">
                    <span style="background-color: rgba(179, 27, 27, 0.05); padding: 4px 8px; border-radius: 4px;">
                        <span style="color: var(--arxiv-red);">📄</span> arXiv:{paper_code} <span style="font-size: 0.8em;">↗</span>
                    </span>
                </a>
            </div>
            {punchline_div}
        </div>
        '''
        
        st.markdown(citation_html, unsafe_allow_html=True)
        
        # Hidden button to handle tab switching after state is set
        if paper_code == st.session_state.get("arxiv_code"):
            click_tab(3)
            st.session_state.pop("arxiv_code", None)  # Clear it after use


def generate_paper_table(df, extra_key=""):
    """Create a stylized table view of papers with key information."""
    # Add custom styling for the table
    st.markdown("""
    <style>
    .paper-row {
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        padding: 8px 0;
        margin-bottom: 8px;
    }
    .paper-row:hover {
        background-color: rgba(179, 27, 27, 0.05);
    }
    .paper-header {
        font-weight: bold;
        border-bottom: 2px solid rgba(179, 27, 27, 0.3);
        padding-bottom: 10px;
        margin-bottom: 12px;
    }
    .title-link {
        font-weight: bold;
        text-decoration: none;
        display: block;
        margin-bottom: 4px;
    }
    .title-link:hover {
        text-decoration: underline;
    }
    .paper-cell {
        padding: 4px 0;
    }
    .read-more-btn {
        background-color: var(--arxiv-red, #b31b1b);
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 14px;
        cursor: pointer;
        transition: background-color 0.2s;
        white-space: nowrap;
    }
    .read-more-btn:hover {
        background-color: var(--arxiv-red-light, #c93232);
    }
    
    /* Button width constraint */
    [data-testid="stHorizontalBlock"] button {
        max-width: 120px !important;
        margin: 0 auto !important;
    }
    
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .paper-row:hover {
            background-color: rgba(179, 27, 27, 0.1);
        }
        .paper-header {
            border-bottom-color: rgba(179, 27, 27, 0.4);
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create a header row with styled headers
    header_cols = st.columns([3, 0.8, 0.8, 1.2, 1])
    st.markdown("<div class='paper-header'>", unsafe_allow_html=True)
    header_cols[0].markdown("**Title**")
    header_cols[1].markdown("**Citations**")
    header_cols[2].markdown("**Influential Citations**")
    header_cols[3].markdown("**Published**")
    header_cols[4].markdown("") # Empty header for action column
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Format function for titles
    def format_title(row):
        title = row['title'].replace("\n", "")
        star = "⭐️ " if row.get('influential_citation_count', 0) > 0 else ""
        return f"{star}{title}"
    
    # Create a simple table with all papers
    for i, paper in df.iterrows():
        paper_code = paper['arxiv_code']
        title = format_title(paper)
        citations = int(paper.get('citation_count', 0))
        influential = int(paper.get('influential_citation_count', 0))
        published = pd.to_datetime(paper['published']).strftime("%b %d, %Y")
        
        # Create a container for the row
        st.markdown("<div class='paper-row'>", unsafe_allow_html=True)
        
        # Create a row for each paper
        cols = st.columns([3, 0.8, 0.8, 1.2, 1])
        
        # Get punchline for tooltip if available
        punchline = paper.get("punchline", "")
        if isinstance(punchline, str) and punchline:
            # Escape HTML and quotes in punchline to avoid breaking the HTML
            punchline = punchline.replace("'", "&#39;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
            punchline_text = f" title=\"{punchline}\""
        else:
            punchline_text = ""
        
        # Add URL to title
        paper_url = paper.get("url", "")
        title_html = f"<a href='{paper_url}' target='_blank' class='title-link' style='color: var(--arxiv-red);'{punchline_text}>{title}</a>"
        
        # Add authors truncated
        authors = paper.get("authors", "")
        if len(authors) > 70:
            authors = authors[:70] + "..."
        authors_html = f"<div style='font-size: 0.85em; color: var(--text-color, #666);'>{authors}</div>"
        
        # Combine title and authors
        cols[0].markdown(f"{title_html}{authors_html}", unsafe_allow_html=True)
        
        # Format counts with nice styling and SVG icons
        cols[1].markdown(f"""<div class='paper-cell' style='text-align: center;'>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; opacity: 0.7; margin-right: 3px;"><path d="M17 6.1H3M21 12.1H3M21 18.1H3"></path></svg>
            {citations}
        </div>""", unsafe_allow_html=True)
        
        cols[2].markdown(f"""<div class='paper-cell' style='text-align: center;'>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; opacity: 0.7; margin-right: 3px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
            {influential}
        </div>""", unsafe_allow_html=True)
        
        # Date with nice styling and calendar icon
        cols[3].markdown(f"""<div class='paper-cell'>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; opacity: 0.7; margin-right: 3px;"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
            {published}
        </div>""", unsafe_allow_html=True)
        
        # Button styled as HTML but triggered by Streamlit button with width constraint (set in CSS)
        if cols[4].button("Read More", key=f"btn_{paper_code}_{extra_key}", use_container_width=True):
            st.session_state.arxiv_code = paper_code
            click_tab(3)
            st.rerun()
            
        st.markdown("</div>", unsafe_allow_html=True)


def create_pagination(items, items_per_page, label="summaries", year=None):
    num_items = len(items)
    num_pages = num_items // items_per_page
    if num_items % items_per_page != 0:
        num_pages += 1

    st.session_state["num_pages"] = num_pages

    if not st.session_state.all_years and year is not None:
        st.markdown(f"**{num_items} papers found for {year}.**")
    else:
        st.markdown(f"**{num_items} papers found.**")
    st.markdown(f"**Pg. {st.session_state.page_number + 1} of {num_pages}**")
    prev_button, mid, next_button = st.columns((1, 10, 1))
    prev_clicked = prev_button.button("Prev", key=f"prev_{label}")
    next_clicked = next_button.button("Next", key=f"next_{label}")

    if prev_clicked and "page_number" in st.session_state:
        st.session_state.page_number = max(0, st.session_state.page_number - 1)
    if next_clicked and "page_number" in st.session_state:
        st.session_state.page_number = min(
            num_pages - 1, st.session_state.page_number + 1
        )

    start_index = st.session_state.page_number * items_per_page
    end_index = min(start_index + items_per_page, num_items)

    return items[start_index:end_index]


def create_bottom_navigation(label: str):
    num_pages = st.session_state["num_pages"]
    st.write(f"**Pg. {st.session_state.page_number + 1} of {num_pages}**")
    prev_button_btm, _, next_button_btm = st.columns((1, 10, 1))
    prev_clicked_btm = prev_button_btm.button("Prev", key=f"prev_{label}_btm")
    next_clicked_btm = next_button_btm.button("Next", key=f"next_{label}_btm")
    if prev_clicked_btm and "page_number" in st.session_state:
        st.session_state.page_number = max(0, st.session_state.page_number - 1)
        st.rerun()
    if next_clicked_btm and "page_number" in st.session_state:
        st.session_state.page_number = min(
            num_pages - 1, st.session_state.page_number + 1
        )
        st.rerun()


def click_tab(tab_num):
    js = f"""
    <script>
        (() => {{
            var tabs = window.parent.document.querySelectorAll("[id^='tabs-bui'][id$='-tab-{tab_num}']");
            if (tabs.length > 0) {{
                tabs[0].click();
            }} else {{
                console.log("Tab with id '-tab-{tab_num}' not found");
            }}
        }})();
    </script>
    """
    st.components.v1.html(js)


def generate_mini_paper_table(df, n=5, extra_key=""):
    """ Create a compact table of top papers for dashboard display. """
    # Add custom styling for the mini table
    st.markdown("""
    <style>
    .mini-paper-row {
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        padding: 4px 0;
        margin-bottom: 4px;
        font-size: 0.9em;
    }
    .mini-paper-row:hover {
        background-color: rgba(179, 27, 27, 0.05);
    }
    .mini-paper-header {
        font-weight: bold;
        border-bottom: 2px solid rgba(179, 27, 27, 0.3);
        padding-bottom: 5px;
        margin-bottom: 8px;
        font-size: 0.9em;
    }
    .mini-title-link {
        font-weight: bold;
        text-decoration: none;
        display: block;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .mini-title-link:hover {
        text-decoration: underline;
    }
    .mini-read-more-btn {
        background-color: var(--arxiv-red, #b31b1b);
        color: white;
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 12px;
        cursor: pointer;
        transition: background-color 0.2s;
        white-space: nowrap;
    }
    .mini-read-more-btn:hover {
        background-color: var(--arxiv-red-light, #c93232);
    }
    
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        .mini-paper-row:hover {
            background-color: rgba(179, 27, 27, 0.1);
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Only take the top n papers
    display_df = df.head(n) if len(df) > n else df
    
    # Create a header row with styled headers
    header_cols = st.columns([3, 0.8, 0.7])
    st.markdown("<div class='mini-paper-header'>", unsafe_allow_html=True)
    header_cols[0].markdown("**Title**")
    header_cols[1].markdown("**Citations**")
    header_cols[2].markdown("") # Empty header for action column
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Format function for titles, reused from generate_paper_table
    def format_title(row):
        title = row['title'].replace("\n", "")
        star = "⭐️ " if row.get('influential_citation_count', 0) > 0 else ""
        return f"{star}{title}"
    
    # Create a simple table with top papers
    for _, paper in display_df.iterrows():
        paper_code = paper['arxiv_code']
        title = format_title(paper)
        citations = int(paper.get('citation_count', 0))
        
        # Create a container for the row
        st.markdown("<div class='mini-paper-row'>", unsafe_allow_html=True)
        
        # Create a row for each paper
        cols = st.columns([3, 0.8, 0.7])
        
        # Add URL to title
        paper_url = paper.get("url", "")
        title_html = f"<a href='{paper_url}' target='_blank' class='mini-title-link' style='color: var(--arxiv-red);'>{title}</a>"
        
        # Add authors truncated
        authors = paper.get("authors", "")
        if len(authors) > 50:  # Shorter than in generate_paper_table for mini view
            authors = authors[:50] + "..."
        authors_html = f"<div style='font-size: 0.8em; color: var(--text-color, #666);'>{authors}</div>"
        
        # Combine title and authors
        cols[0].markdown(f"{title_html}{authors_html}", unsafe_allow_html=True)
        
        # Format citation count with icon
        cols[1].markdown(f"""<div style='text-align: center;'>
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; opacity: 0.7; margin-right: 3px;"><path d="M17 6.1H3M21 12.1H3M21 18.1H3"></path></svg>
            {citations}
        </div>""", unsafe_allow_html=True)
        
        # Button styled with width constraint
        if cols[2].button("Read More", key=f"mini_btn_{paper_code}_{extra_key}", use_container_width=True):
            st.session_state.arxiv_code = paper_code
            click_tab(3)
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    if len(df) > n:
        st.caption(f"Showing top {n} of {len(df)} papers")


def create_featured_paper_card(paper: Dict) -> None:
    """Creates a featured paper card using the weekly highlight. """
    st.markdown("### Featured Paper")
    paper_code = paper.get("arxiv_code", "")
    punchline = paper.get("punchline", "")
    st.markdown(f"#### *{paper.get('title', 'Featured Paper')}*")
    st.image(
        f"https://arxiv-art.s3.amazonaws.com/{paper_code}.png",
        # use_container_width=True,
        width=450
    )    
    st.markdown(f"*{punchline}*")
    if st.button("Read More", key=f"featured_{paper_code}", use_container_width=True):
        st.session_state.arxiv_code = paper_code
        click_tab(3)


def display_interesting_facts(facts_list, n_cols=2, papers_df=None):
    """ Displays a grid of interesting facts from papers. """
    if not facts_list:
        st.info("No interesting facts found.")
        return
    
    # Add custom styling for dark mode compatibility
    st.markdown("""
    <style>
    /* Dark mode support for fact cards */
    @media (prefers-color-scheme: dark) {
        .fact-card {
            background-color: var(--background-color, rgba(49, 51, 63, 0.4)) !important;
            border-left-color: var(--primary-color, #FF4B4B) !important;
        }
        .fact-card a {
            color: var(--link-color, #8ab4f8) !important;
        }
        .fact-topic {
            background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.2)) !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
        
    # Create a multi-column layout
    cols = st.columns(n_cols)
    
    # Distribute facts among columns
    for i, fact in enumerate(facts_list):
        col_idx = i % n_cols
        
        # Get topic if papers_df is provided
        topic = None
        topic_full = None
        if papers_df is not None and 'arxiv_code' in fact:
            arxiv_code = fact['arxiv_code']
            if arxiv_code in papers_df.index and 'topic' in papers_df.columns:
                topic_full = papers_df.loc[arxiv_code, 'topic']
                topic = topic_full[:30] + "..." if len(topic_full) > 30 else topic_full

        
        with cols[col_idx]:
            # Create a container with padding and subtle border
            with st.container():
                st.markdown(
                    f"""<div class="fact-card" style="
                        padding: 1em;
                        margin-bottom: 1em;
                        background-color: var(--background-color, #f9f9f9);
                        border-left: 3px solid var(--primary-color, #FF4B4B);
                        border-radius: 5px;
                    ">
                    <p style="font-size: 1.0em; margin-bottom: 0.5em;">{fact['fact']}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                        {"<span class='fact-topic' style='background-color: var(--secondary-background-color, rgba(128, 128, 128, 0.1)); padding: 3px 8px; border-radius: 12px; font-size: 0.7em;' title='" + topic_full + "'>" + topic + "</span>" if topic else ""}
                        <p style="
                            font-size: 0.8em;
                            font-style: italic;
                            color: var(--text-color, #888);
                            margin: 0;
                            text-align: right;
                            flex-grow: 1;
                        ">
                        <a href="https://arxiv.org/abs/{fact['arxiv_code']}" target="_blank" style="text-decoration: none;">
                            {fact['paper_title'][:75] + ('...' if len(fact['paper_title']) > 75 else '')}
                        </a>
                        </p>
                    </div>
                    </div>""",
                    unsafe_allow_html=True
                )
