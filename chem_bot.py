print("=== CHEMISTRY PYTHON SCRIPT INITIALIZED ===", flush=True)

import os
import json
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from jobspy import scrape_jobs

SEEN_JOBS_FILE = "seen_chem_jobs.json"

# -------------------------------------------------------------
# BROADER CANADIAN & US REGIONAL BASEROUTES
# -------------------------------------------------------------
BASELINE_LOCATIONS = [
    # --- British Columbia (Vancouver/GVRD, Victoria, Kelowna) ---
    "vancouver", "bc", "b.c.", "british columbia", "remote", "burnaby", "richmond", 
    "surrey", "delta", "langley", "coquitlam", "north van", "north vancouver", 
    "new westminster", "port moody", "maple ridge", "white rock", "abbotsford", 
    "lower mainland", "greater vancouver", "gvrd", "vancouver island",
    "victoria", "saanich", "langford", "esquimalt", "kelowna", "vernon", "penticton", "west kelowna",

    # --- Alberta (Calgary, Edmonton) ---
    "calgary", "edmonton", "alberta", "ab", "sherwood park", "st. albert", "lethbridge", "red deer",

    # --- Manitoba (Winnipeg) ---
    "winnipeg", "manitoba", "mb", "st. boniface", "headingley",

    # --- Ontario (Markham, Toronto / GTA) ---
    "markham", "toronto", "ontario", "on", "gta", "greater toronto area", 
    "mississauga", "vaughan", "richmond hill", "scarborough", "etobicoke", 
    "north york", "brampton", "oakville", "waterloo", "kitchener", "hamilton", "ottawa",

    # --- Quebec (Montreal) ---
    "montreal", "quebec", "qc", "laval", "longueuil", "brossard", "dorval", "saint-laurent",

    # --- General Canada ---
    "canada",

    # --- US States (WA, OR, CA) - 50 Mile Broad Scope ---
    "washington", "wa", "seattle", "redmond", "bellevue", "tacoma", "everett", "olympia",
    "oregon", "or", "portland", "beaverton", "salem", "eugene", "gresham", "hillsboro",
    "california", "bay area", "socal", "norcal", "silicon valley", "los angeles", 
    "san francisco", "san jose", "palo alto", "mountain view", "sunnyvale", "santa clara", 
    "fremont", "san diego", "irvine", "sacramento", "oakland", "berkeley", "pasadena"
]

# Company location overrides to catch facilities outside primary city inputs
COMPANY_LOCATION_OVERRIDES = {
    "abcellera": ["vancouver", "bc"],
    "zymeworks": ["vancouver", "bc"],
    "stemcell": ["vancouver", "bc", "burnaby"],
    "methanex": ["vancouver", "bc"],
    "nova chemicals": ["calgary", "alberta", "red deer", "joffre"],
    "bayer": ["calgary", "alberta", "toronto", "ontario"],
}

safe_override_codes = [", bc", ", on", ", ab", ", mb", ", qc", ", wa", ", or", ", ca"]

INTERN_KEYWORDS = ["intern", "internship", "coop", "co-op", "student"]

# -------------------------------------------------------------
# CHEMISTRY, CHEMICAL SCIENCES & BIOTECH TARGET FIELDS
# -------------------------------------------------------------
TARGET_FIELD_KEYWORDS = [
    "chemistry", "chemist", "chemical", "biochemistry", "biochemical",
    "analytical", "lab", "laboratory", "assay", "formulation",
    "polymer", "materials science", "material science", "spectroscopy",
    "chromatography", "hplc", "gc-ms", "r&d", "research and development",
    "quality control", "qc", "qa/qc", "scientist", "junior chemist",
    "biotech", "life sciences", "process engineer", "chemical engineer",
    "assay development", "biologics", "immunology", "toxicology", "pharmacology"
]

EXCLUDED_KEYWORDS = [
    "software", "swe", "civil", "structural", "hvac", "plumbing", 
    "geotechnical", "sales", "nurse", "medical doctor", "dentist"
]

# -------------------------------------------------------------
# DIRECT CHEMISTRY, PHARMA & BIOTECH EMPLOYER BOARDS
# -------------------------------------------------------------
CUSTOM_GREENHOUSE_COMPANIES = [
    "abcellera", "zymeworks", "stemcell"
]

CUSTOM_DIRECT_BOARDS = [
    {"name": "Aspect Biosystems", "url": "https://aspectbiosystems.com/careers/", "type": "html"},
    {"name": "StarFish Medical", "url": "https://starfishmedical.com/careers/", "type": "html"},
    {"name": "Zymeworks", "url": "https://zymeworks.com/careers/", "type": "html"},
    {"name": "STEMCELL Technologies", "url": "https://www.stemcell.com/careers.html", "type": "html"},
    {"name": "Methanex", "url": "https://www.methanex.com/careers", "type": "html"},
    {"name": "NOVA Chemicals", "url": "https://www.novachem.com/careers/", "type": "html"},
]


def is_location_allowed(location_str, company_name=""):
    if not location_str:
        return True  
    
    loc_lower = str(location_str).lower()
    comp_lower = str(company_name).lower()
    
    if any(loc in loc_lower for loc in BASELINE_LOCATIONS):
        return True

    if ", ca" in loc_lower or " ca " in loc_lower or "canada" in loc_lower or ", bc" in loc_lower or ", on" in loc_lower or ", qc" in loc_lower or ", ab" in loc_lower or ", mb" in loc_lower:
        return True

    for key, allowed_regions in COMPANY_LOCATION_OVERRIDES.items():
        if key in comp_lower:
            if any(region in loc_lower for region in allowed_regions):
                return True
            if any(code in loc_lower for code in safe_override_codes):
                return True

    return False


def is_matching_role(title_str):
    if not title_str:
        return False
    title_lower = str(title_str).lower()
    
    if any(ex in title_lower for ex in EXCLUDED_KEYWORDS):
        return False
        
    has_intern = any(kw in title_lower for kw in INTERN_KEYWORDS)
    has_field = any(kw in title_lower for kw in TARGET_FIELD_KEYWORDS)
    
    return has_intern and has_field


def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_seen_jobs(seen_ids):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen_ids), f)


def fetch_custom_employer_jobs():
    employer_jobs = []
    print("Checking chemistry & biotech employer boards...", flush=True)

    # Greenhouse Check
    for company in CUSTOM_GREENHOUSE_COMPANIES:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                for job in data.get("jobs", []):
                    title = job.get("title", "")
                    location = job.get("location", {}).get("name", "")
                    if is_matching_role(title) and is_location_allowed(location, company):
                        employer_jobs.append({
                            "id": f"gh-{company}-{job.get('id')}",
                            "title": title,
                            "company": company.capitalize(),
                            "location": location if location else "Regional/Remote",
                            "job_url": job.get("absolute_url")
                        })
        except Exception as e:
            print(f"Error fetching Greenhouse board for {company}: {e}", flush=True)

    # Direct Board Scrape
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for board in CUSTOM_DIRECT_BOARDS:
        name = board["name"]
        url = board["url"]
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for a_tag in soup.find_all('a', href=True):
                    title = a_tag.get_text(strip=True)
                    job_url = a_tag['href']
                    if not job_url.startswith("http"):
                        job_url = urljoin(url, job_url)

                    if is_matching_role(title):
                        employer_jobs.append({
                            "id": f"dir-{name.lower().replace(' ', '-')}-{abs(hash(job_url))}",
                            "title": title,
                            "company": name,
                            "location": "Regional/Remote",
                            "job_url": job_url
                        })
        except Exception as e:
            print(f"Error scraping direct board for {name}: {e}", flush=True)

    return employer_jobs


def run_bot():
    print("Starting Chemistry Bot run_bot()...", flush=True)
    
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("❌ ERROR: DISCORD_WEBHOOK_URL is missing or empty!", flush=True)
        return

    seen_ids = load_seen_jobs()
    print(f"Loaded {len(seen_ids)} previously seen chemistry job IDs from cache.", flush=True)
    
    new_jobs = []

    direct_jobs = fetch_custom_employer_jobs()
    for job in direct_jobs:
        if job["id"] not in seen_ids and job["job_url"]:
            new_jobs.append(job)
            seen_ids.add(job["id"])

    # Broad Canadian & US Aggregator Targets with 50 Mile Radius
    print("Scraping LinkedIn and Indeed for chemistry & chemical internships...", flush=True)
    search_queries = [
        "Chemistry Chemist Intern Co-Op Internship",
        "Analytical Chemistry Biochemistry Laboratory Intern",
        "Chemical Science Research Intern Student"
    ]
    
    search_targets = [
        # BC Hubs
        {"location": "Vancouver, BC", "country": "Canada", "distance": 50},
        {"location": "Victoria, BC", "country": "Canada", "distance": 50},
        {"location": "Kelowna, BC", "country": "Canada", "distance": 50},
        # Alberta & Manitoba
        {"location": "Calgary, AB", "country": "Canada", "distance": 50},
        {"location": "Edmonton, AB", "country": "Canada", "distance": 50},
        {"location": "Winnipeg, MB", "country": "Canada", "distance": 50},
        # Ontario & Quebec
        {"location": "Markham, ON", "country": "Canada", "distance": 50},
        {"location": "Toronto, ON", "country": "Canada", "distance": 50},
        {"location": "Montreal, QC", "country": "Canada", "distance": 50},
        # US States (WA, OR, CA) - 50 Mile Radius
        {"location": "Seattle, WA", "country": "USA", "distance": 50},
        {"location": "Portland, OR", "country": "USA", "distance": 50},
        {"location": "San Francisco, CA", "country": "USA", "distance": 50},
        {"location": "Los Angeles, CA", "country": "USA", "distance": 50}
    ]

    for target in search_targets:
        loc_str = target["location"]
        country_str = target["country"]
        dist = target["distance"]

        for query in search_queries:
            try:
                jobs = scrape_jobs(
                    site_name=["linkedin", "indeed"],
                    search_term=query,
                    location=loc_str,
                    country_indeed=country_str,
                    distance=dist,
                    hours_old=24,
                    results_wanted=35,
                )

                if jobs is not None and not jobs.empty:
                    for _, row in jobs.iterrows():
                        job_id = str(row['id']) if ('id' in row and row['id']) else str(row['job_url'])
                        title = row.get('title', 'Chemistry Intern')
                        company = row.get('company', 'Unknown Company')
                        location = str(row.get('location', loc_str))
                        
                        if job_id not in seen_ids and is_location_allowed(location, company) and is_matching_role(title):
                            new_jobs.append({
                                "id": job_id,
                                "title": title,
                                "company": company,
                                "location": location,
                                "job_url": row.get('job_url', '')
                            })
                            seen_ids.add(job_id)
            except Exception as e:
                print(f"Error running JobSpy scraper for '{query}' in '{loc_str}': {e}", flush=True)

    if not new_jobs:
        print("No new chemistry internships found today.", flush=True)
        save_seen_jobs(seen_ids)
        return

    grouped_jobs = {}
    for job in new_jobs:
        comp = job['company']
        if comp not in grouped_jobs:
            grouped_jobs[comp] = []
        grouped_jobs[comp].append(job)

    message_lines = [f"**🧪 Found {len(new_jobs)} New Chemistry/Biotech Internship(s)!**\n"]
    
    for company, jobs_list in sorted(grouped_jobs.items()):
        message_lines.append(f"🏢 **{company}**")
        for job in jobs_list:
            title = job['title']
            location = job['location']
            url = job['job_url']
            message_lines.append(f"  • **{title}** ({location})\n    🔗 <{url}>")
        message_lines.append("")

    full_text = "\n".join(message_lines)

    if len(full_text) > 1900:
        chunks = [full_text[i:i+1900] for i in range(0, len(full_text), 1900)]
        for chunk in chunks:
            res = requests.post(webhook_url, json={"content": chunk})
            res.raise_for_status()
    else:
        res = requests.post(webhook_url, json={"content": full_text})
        res.raise_for_status()

    save_seen_jobs(seen_ids)
    print(f"Successfully posted {len(new_jobs)} chemistry listings to Discord.", flush=True)


if __name__ == "__main__":
    print("Executing chemistry main block...", flush=True)
    run_bot()
