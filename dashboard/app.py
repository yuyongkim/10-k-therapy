
import streamlit as st
import pandas as pd
import json
import os
import glob
from pathlib import Path
import plotly.express as px

# Page Config
st.set_page_config(page_title="SEC License DB", layout="wide")

# Paths
DATA_DIR = Path("data/extracted_licenses")

# --- Helper Functions ---

@st.cache_data
def load_litigation_data():
    """Loads litigation royalties data from CSV exports."""
    # Try multiple base paths. Override via EXPORTS_DIR env var if needed.
    base_paths = [
        Path(os.environ.get("EXPORTS_DIR", "data/exports")),
        Path("data/exports"),
        Path("../data/exports"),
    ]
    
    all_files = []
    for base in base_paths:
        if base.exists():
            found = list(base.glob("litigation_royalties_*.csv"))
            all_files.extend(found)
            
    if not all_files:
        return pd.DataFrame()
    
    # Load the latest file
    latest_file = max(all_files, key=os.path.getctime)
    df = pd.read_csv(latest_file)
    return df

@st.cache_data
def load_company_mapping():
    """Load CIK to Company Name mapping from tickers JSON."""
    mapping = {}
    try:
        # Try multiple paths for robustness. Override via COMPANY_TICKERS_PATH env var.
        paths = [
            Path(os.environ.get("COMPANY_TICKERS_PATH", "data/company_tickers.json")),
            Path("../data/company_tickers.json"),
            Path("data/company_tickers.json"),
        ]
        
        json_path = next((p for p in paths if p.exists()), None)
        
        if json_path:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Link CIK to Title
            for key, val in data.items():
                cik_str = str(val.get('cik_str', '')).zfill(10)
                title = val.get('title', '')
                mapping[cik_str] = title
    except Exception as e:
        print(f"Error loading company mapping: {e}")
    
    return mapping

@st.cache_data(ttl=60) # Refresh every minute
def load_data():
    all_data = []
    
    # Load CIK mapping
    cik_map = load_company_mapping()
    
    # 1. Load recursive footnote extractions (Existing Data)
    # Search in default data directory and parent directory
    search_paths = [
        DATA_DIR,
        Path("../data/extracted_licenses").resolve()
    ]
    
    recursive_files = []
    for p in search_paths:
        if p.exists():
            print(f"Searching in: {p}")
            recursive_files.extend(list(p.rglob("license_agreements.json")))
            
    print(f"Found {len(recursive_files)} existing license files.")
    
    for f in recursive_files:
        try:
            # Try to infer CIK from path: .../data/extracted_licenses/{cik}/...
            # Path parts might be: ... / {cik} / {filing_type} / {accession} / license_agreements.json
            path_cik = None
            try:
                # Iterate parts to find something that looks like a CIK (10 digits)
                for part in f.parts:
                    if part.isdigit() and len(part) == 10:
                        path_cik = part
                        break
            except Exception:
                pass

            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, list):
                    for item in data:
                        # Get Extraction
                        extraction = item.get('extraction', {})
                        if not extraction: 
                            # Fallback if extraction is missing but data exists in item
                            if item.get('agreements') or item.get('financial_terms'):
                                extraction = item
                            else:
                                continue
                            
                        # Normalize Data
                        # The 'Company' column should represent the filing company, which we infer from CIK
                        company_name_from_extraction = item.get('source_note', {}).get('company_name') or \
                                                       item.get('source_meta', {}).get('company_name') or \
                                                       'Unknown'
                        
                        # Fix: If company name is generic or unknown, use the CIK mapping
                        mapped_name = cik_map.get(str(path_cik), "Unknown") if path_cik else "Unknown"
                        
                        # Prioritize Mapped Name if Extracted is bad or if we have a CIK
                        final_company_name = company_name_from_extraction
                        if mapped_name != "Unknown":
                            final_company_name = mapped_name
                        elif final_company_name in ["Unknown", "None", "To be determined"]:
                            final_company_name = mapped_name # Will still be "Unknown" if no map

                        confidence = extraction.get('metadata', {}).get('confidence_score') or extraction.get('confidence_score', 0.0)
                        
                        # Extract financial data from nested 'agreements' if present
                        agreements_list = extraction.get('agreements', [])
                        if agreements_list:
                            # Use first agreement for simplicity
                            first_ag = agreements_list[0] if isinstance(agreements_list, list) else {}
                            fin_terms = first_ag.get('financial_terms', {})
                            upfront = fin_terms.get('upfront_payment', {})
                            royalty = fin_terms.get('royalty', {})
                            
                            upfront_amount = upfront.get('amount')
                            royalty_rate = royalty.get('rate')
                            
                            parties = first_ag.get('parties', {})
                            licensor_name = parties.get('licensor', {}).get('name')
                            licensee_name = parties.get('licensee', {}).get('name')
                            tech = first_ag.get('technology', {})
                            tech_name = tech.get('name')
                            tech_category = tech.get('category')  # Use as Type fallback
                            ag_confidence = first_ag.get('metadata', {}).get('confidence_score', confidence)
                            agreement_type = first_ag.get('agreement_type')
                            date = first_ag.get('date')
                        else:
                            # Fallback to direct extraction structure
                            fin_terms = extraction.get('financial_terms', {})
                            upfront = fin_terms.get('upfront_payment', {})
                            royalty = fin_terms.get('royalty', {})
                            
                            upfront_amount = upfront.get('amount')
                            royalty_rate = royalty.get('rate')
                            
                            parties = extraction.get('parties', {})
                            licensor_name = parties.get('licensor', {}).get('name')
                            licensee_name = parties.get('licensee', {}).get('name')
                            tech_name = extraction.get('technology', {}).get('name')
                            tech_category = extraction.get('technology', {}).get('category')  # Fallback Type
                            ag_confidence = confidence
                            agreement_type = extraction.get('agreement_type')
                            date = extraction.get('date')
                        
                        # --- FILTER: Relaxed filtering to show more data ---
                        # Previously: (upfront_amount is not None) or (royalty_rate is not None)
                        # New: Include if we have Company and (Type or Parties or Financials)
                        has_financial = (upfront_amount is not None) or (royalty_rate is not None)
                        has_parties = (licensor_name and licensor_name != "Unknown") or (licensee_name and licensee_name != "Unknown")
                        
                        # Only skip if we have absolutely nothing useful
                        if not (has_financial or has_parties or agreement_type):
                            continue 
                        
                        row = {
                            "Company": final_company_name,
                            "CIK": path_cik,
                            "Title": item.get('source_meta', {}).get('title') or extraction.get('metadata', {}).get('title'),
                            "Type": agreement_type or tech_category,
                            "Licensor": licensor_name,
                            "Licensee": licensee_name,
                            "Technology": tech_name,
                            "Upfront Payment": upfront_amount,
                            "Royalty Rate": royalty_rate,
                            "Date": date,
                            "Confidence": ag_confidence,
                            "raw_data": item
                        }
                        all_data.append(row)
        except Exception as e:
            # print(f"Error loading {f}: {e}")
            continue

    # 2. Load new batch extractions (Flat files)
    flat_files = glob.glob(str(DATA_DIR / "extracted_*.json"))
    for f in flat_files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                for item in data:
                    extraction = item.get('extraction', {})
                    meta = item.get('source_meta', {})
                    
                    row = {
                        "Company": meta.get('company_name'),
                        "CIK": meta.get('cik'),
                        "Title": meta.get('title'),
                        "Type": extraction.get('agreement_type'),
                        "Licensor": extraction.get('parties', {}).get('licensor', {}).get('name'),
                        "Licensee": extraction.get('parties', {}).get('licensee', {}).get('name'),
                        "Technology": extraction.get('technology', {}).get('name'),
                        "Date": extraction.get('date'),
                        "Confidence": extraction.get('confidence_score'),
                        "raw_data": item
                    }
                    all_data.append(row)
        except Exception as e:
            continue
            
    if not all_data:
        return pd.DataFrame()
        
    return pd.DataFrame(all_data)

# --- Main Dashboard Logic ---
def main():
    st.sidebar.title("License Viewer")
    
    # Dataset Selection
    dataset_choice = st.sidebar.radio("Select Dataset", ["SEC License Agreements", "Litigation Royalties"])

    st.sidebar.markdown("Checking `data/extracted_licenses`...")
    if st.sidebar.button("Refresh Data"):
        load_data.clear()
        load_litigation_data.clear()
        st.rerun()

    # --- 1. Litigation Royalties View ---
    if dataset_choice == "Litigation Royalties":
        st.title("⚖️ Litigation Royalties Analysis")
        df_lit = load_litigation_data()

        if df_lit.empty:
            st.warning("No litigation data found in `data/exports`. Please check the crawler exports.")
        else:
            # Metrics
            total_cases = len(df_lit)
            royalty_rate_count = df_lit['Royalty Rate'].notna().sum()
            total_damages_entries = df_lit['Damages'].notna().sum() if 'Damages' in df_lit.columns else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Cases", total_cases)
            col2.metric("Royalty Rates Found", royalty_rate_count)
            col3.metric("Damages Found", total_damages_entries)

            st.divider()

            # Visualizations
            c1, c2 = st.columns(2)
            with c1:
                if 'Industry' in df_lit.columns:
                    st.subheader("Results by Industry")
                    industry_counts = df_lit['Industry'].value_counts().reset_index()
                    industry_counts.columns = ['Industry', 'Count']
                    fig_ind = px.bar(industry_counts, x='Industry', y='Count')
                    st.plotly_chart(fig_ind, use_container_width=True)
            
            with c2:
                if 'Royalty Type' in df_lit.columns:
                    st.subheader("Royalty Type Distribution")
                    type_counts = df_lit['Royalty Type'].value_counts().reset_index()
                    type_counts.columns = ['Royalty Type', 'Count']
                    fig_type = px.pie(type_counts, values='Count', names='Royalty Type')
                    st.plotly_chart(fig_type, use_container_width=True)

            # Data Table
            st.subheader("Detailed Litigation Data")
            st.dataframe(df_lit, use_container_width=True)

    # --- 2. SEC License Agreements View ---
    else:
        st.title("📊 SEC License Agreements Analysis")
        
        # Load Data
        df = load_data()
        
        st.markdown(f"**Loaded {len(df)} agreements**")

        if df.empty:
            st.info("No data extracted yet. The extractor is running in the background. Please wait a moment and refresh.")
            st.stop()

        # Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Agreements", len(df))
        col2.metric("Unique Licensors", df['Licensor'].nunique())
        col3.metric("Unique Licensees", df['Licensee'].nunique())

        st.divider()

        # Charts
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Agreement Types")
            type_counts = df['Type'].value_counts()
            st.bar_chart(type_counts)

        with c2:
            st.subheader("Top 10 Licensors")
            top_licensors = df['Licensor'].value_counts().head(10)
            st.bar_chart(top_licensors)

        st.divider()

        # Search & Filter
        st.subheader("🔍 Search & Filter")
        col_search, col_type = st.columns([2, 1])
        search_term = col_search.text_input("Search Company or Tech", "")
        
        # Safe filter for multiselect
        available_types = df['Type'].unique().tolist() if 'Type' in df.columns else []
        type_filter = col_type.multiselect("Agreement Type", available_types)

        # Apply Filters
        filtered_df = df.copy()
        if search_term:
            # Safe text search
            mask = pd.Series(False, index=filtered_df.index)
            for col in ['Company', 'Technology', 'Licensor']:
                if col in filtered_df.columns:
                    mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
            filtered_df = filtered_df[mask]
            
        if type_filter:
            filtered_df = filtered_df[filtered_df['Type'].isin(type_filter)]

        st.write(f"Showing {len(filtered_df)} filtered results")

        # Data Table
        SHOW_LIMIT = 1000
        if len(filtered_df) > SHOW_LIMIT:
            st.warning(f"⚠️ Dataset is large ({len(filtered_df)} rows). Showing top {SHOW_LIMIT} rows for performance.")
            if st.checkbox("Show ALL rows (May be slow)"):
                st.dataframe(filtered_df, use_container_width=True)
            else:
                st.dataframe(filtered_df.head(SHOW_LIMIT), use_container_width=True)
        else:
            st.dataframe(filtered_df, use_container_width=True)
            
        # Select for Detail View
        if not filtered_df.empty:
            st.divider()
            st.subheader("📄 Agreement Details")
            
            # Create a selection list
            options = filtered_df.apply(lambda x: f"{x.get('Company', 'Unknown')} - {x.get('Type', 'Unknown')} ({x.get('Date', 'N/A')})", axis=1).tolist()
            selected_option = st.selectbox("Select Agreement to View Details", [""] + options)
            
            if selected_option and selected_option != "":
                idx = options.index(selected_option) # Correct index
                if 0 <= idx < len(filtered_df):
                    row = filtered_df.iloc[idx]
                    raw_item = row.get('raw_data', {})
                    extraction = raw_item.get('extraction', {})

                    d1, d2 = st.columns(2)
                    with d1:
                        st.markdown("### Party Details")
                        st.write(f"**Licensor:** {row.get('Licensor')}")
                        st.write(f"**Licensee:** {row.get('Licensee')}")
                        
                        st.markdown("### Technology")
                        st.info(row.get('Technology') or "No description available")
                        
                    with d2:
                        st.markdown("### Financial Terms")
                        fin = extraction.get('financial_terms', {})
                        if fin:
                            st.json(fin)
                        else:
                            st.write("No financial terms extracted.")
                            
                        st.markdown("### Analysis")
                        st.write(f"**Confidence:** {row.get('Confidence')}")
                        st.write(f"**Reasoning:** {extraction.get('reasoning')}")

if __name__ == "__main__":
    main()
