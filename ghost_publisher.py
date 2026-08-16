"""
=============================================================================
Script Name: ghost_publisher.py
Purpose: The 95% HITL Publishing Pipeline (Part 2).
         Reads the generated market_flow_report.html and pushes it to the 
         Ghost.org Admin API as an unpublished Draft.
=============================================================================
"""
import os
import jwt
import requests
import configparser
from datetime import datetime
from estate_env import TARGET_DIR, CONFIG_PATH

def publish_to_ghost():
    print("========================================================")
    print("   ESTATE GHOST.ORG PUBLISHER (Admin API)")
    print("========================================================")
    
    # 1. Load Config
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    
    try:
        ghost_url = config['GHOST']['API_URL'].rstrip('/')
        admin_api_key = config['GHOST']['ADMIN_API_KEY']
    except KeyError:
        print("[!] Error: [GHOST] API_URL or ADMIN_API_KEY missing in estate_config.ini")
        return

    # 2. Read the HTML Report
    html_path = os.path.join(TARGET_DIR, "market_flow_report.html")
    if not os.path.exists(html_path):
        print(f"[!] Error: Could not find {html_path}. Run market_flow_engine first.")
        return
        
    with open(html_path, 'r', encoding='utf-8') as f:
        raw_html = f.read()
        
    # FIX: Wrap the HTML in Ghost's magic tags to prevent the API from stripping our CSS wrapper
    html_content = f"<!--kg-card-begin: html-->\n{raw_html}\n<!--kg-card-end: html-->"

    # 3. Generate JWT Token for Ghost Admin API
    try:
        id, secret = admin_api_key.split(':')
        iat = int(datetime.now().timestamp())
        header = {'alg': 'HS256', 'typ': 'JWT', 'kid': id}
        payload = {
            'iat': iat,
            'exp': iat + 5 * 60,
            'aud': '/admin/'
        }
        token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers=header)
    except Exception as e:
        print(f"[!] Failed to generate Ghost JWT Token. Check your API Key format. Error: {e}")
        return

    # 4. Build the Post Payload
    today_str = datetime.now().strftime("%B %d, %Y")
    
    # Ghost strips <script> tags from raw HTML for security. 
    # We must inject the sorting logic via the official codeinjection_foot API field.
    js_sorting_script = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('th.sortable').forEach(th => {
            th.addEventListener('click', function() {
                const table = this.closest('table');
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr.data-row'));
                const colIdx = Array.from(this.parentNode.children).indexOf(this);
                let asc = this.dataset.asc === 'true';
                this.dataset.asc = !asc;
                
                rows.sort((a, b) => {
                    let valA = a.children[colIdx].getAttribute('data-sort');
                    let valB = b.children[colIdx].getAttribute('data-sort');
                    let numA = parseFloat(valA);
                    let numB = parseFloat(valB);
                    
                    if(!isNaN(numA) && !isNaN(numB)) {
                        return asc ? numA - numB : numB - numA;
                    } else {
                        return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
                    }
                });
                rows.forEach(tr => tbody.appendChild(tr));
            });
        });
    });
    </script>
    """
    
    post_data = {
        "posts": [{
            "title": f"Institutional Market Flow Report - {today_str}",
            "html": html_content,
            "status": "draft",
            "featured": False,
            "tags": [{"name": "Market Flow"}, {"name": "Quantitative Research"}],
            "custom_excerpt": "Automated institutional capital rotation and relative strength matrix.",
            "codeinjection_foot": js_sorting_script
        }]
    }

    # 5. Transmit to Ghost
    headers = {'Authorization': f'Ghost {token}'}
    # FIX: Append ?source=html to force Ghost to parse the raw HTML payload
    url = f"{ghost_url}/ghost/api/admin/posts/?source=html"
    
    print(f"[*] Transmitting draft to {ghost_url}...")
    try:
        response = requests.post(url, json=post_data, headers=headers)
        if response.status_code in [200, 201]:
            print("[+] Success! Market Flow Report uploaded as an unpublished Draft.")
        else:
            print(f"[!] Failed to upload. Status Code: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"[!] Network error during transmission: {e}")

if __name__ == '__main__':
    publish_to_ghost()