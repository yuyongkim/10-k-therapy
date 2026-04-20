from parser.contract_parser import ContractParser
import os

# Relative path from sec-license-extraction root
file_path = "data/raw_filings/0000773840/10-K/0000773840-25-000010/exhibits/EX-10.44_exhibit104412312024.htm"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    # Allow overriding with an absolute path via env var (e.g. when data dir lives elsewhere)
    abs_path = os.environ.get("CONTRACT_PARSER_TEST_PATH")
    if abs_path and os.path.exists(abs_path):
        print("Using CONTRACT_PARSER_TEST_PATH override.")
        file_path = abs_path
    else:
        exit(1)

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

parser = ContractParser(html)
text = parser.get_clean_text()
title = parser.get_title()

print(f"--- Contract Metadata ---")
print(f"Title: {title}")
print(f"Total Length (chars): {len(text)}")
print(f"Preview (first 200 chars):")
print(text[:200])
