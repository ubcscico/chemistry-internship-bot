import os
import json
import time
import requests
from jobspy import scrape_jobs
import pandas as pd

CACHE_FILE = "seen_chem_jobs.json"

def load_seen_jobs():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_jobs(seen_jobs):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(seen_jobs), f)

def send_discord_group(company, jobs_list):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL is not set.")
        return

    message_lines = [f"🏢 **{company}**"]
    for job in jobs_list:
        title = job.get('title', 'N/A')
        location = job.get('location', 'N/A')
        job_url = job.get('job_url', 'N/A')
        message_lines.append(f"• **{title}** ({location})\n  🔗 <{job_url}>")

    payload = {"content": "\n".join(message_lines)}
    
    while True:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 429:
            retry_after = response.json().get("retry_after", 5)
            print(f"Discord rate-limited. Retrying after {retry_after} seconds...", flush=True)
            time.sleep(retry_after)
        else:
            if response.status_code != 204:
                print(f"Failed to send Discord alert: {response.status_code}, {response.text}")
            break

def main():
    print("=== CANADIAN LIFE, MEDICAL & PHARMA SCIENCES BOT INITIALIZED ===")
    
    seen_jobs = load_seen_jobs()
    new_jobs_count = 0

    base_topics = [
        "Biochemistry", "Biologist", "Biology", "Biotechnology", "Biotech",
        "Biomedical", "Bioinformatics", "Molecular Biology", "Cell Biology",
        "Genomics", "Proteomics", "Metabolomics", "Stem Cell", "Immunology",
        "Virology", "Bacteriology", "Microbiology", "Pathology", "Histology",
        "Pharmaceutical", "Biopharmaceutical", "Biopharma", "Drug Discovery",
        "Medicinal Chemistry", "Pharmacokinetics", "Pharmacodynamics", 
        "Formulation Scientist", "Analytical Chemistry", "Biochemist", 
        "Bioanalytical", "Therapeutics", "Preclinical", "Assay", 
        "Regulatory Affairs", "Clinical Operations",
        "Clinical Science", "Medical Science", "Clinical Research", "Clinical Trials",
        "Translational Medicine", "Pathobiology", "Neuroscience", "Physiology", 
        "Hematology", "Oncology", "Cardiovascular Research", "Epidemiology", 
        "Medical Laboratory", "Translational Research",
        "Health Science", "Health Research", "Health Informatics", 
        "Public Health", "Biomedical Science", "RNA", "DNA", 
        "Environmental Science", "Water Quality", "Conservation Science"
    ]

    modifiers = ["intern", "internship", "co-op", "coop"]

    search_queries = []
    for topic in base_topics:
        for mod in modifiers:
            search_queries.append(f"{topic} {mod}")

    search_targets = [
        {"location": "Canada", "country": "Canada"},
        {"location": "Vancouver, BC", "country": "Canada", "distance": 75},
        {"location": "Victoria, BC", "country": "Canada", "distance": 75},
        {"location": "Kelowna, BC", "country": "Canada", "distance": 75},
        {"location": "Calgary, AB", "country": "Canada", "distance": 75},
        {"location": "Edmonton, AB", "country": "Canada", "distance": 75},
        {"location": "Toronto, ON", "country": "Canada", "distance": 75},
        {"location": "Ottawa, ON", "country": "Canada", "distance": 75},
        {"location": "Montreal, QC", "country": "Canada", "distance": 75},
        {"location": "Quebec City, QC", "country": "Canada", "distance": 75}
    ]

    all_jobs = []

    for target in search_targets:
        loc_str = target["location"]
        country_str = target["country"]

        for query in search_queries:
            print(f"Searching for '{query}' in '{loc_str}'...")
            try:
                scrape_args = {
                    "site_name": ["indeed", "linkedin", "zip_recruiter", "glassdoor"],
                    "search_term": query,
                    "location": loc_str,
                    "country_indeed": country_str,
                    "hours_old": 72,
                    "results_wanted": 15
                }
                if "distance" in target:
                    scrape_args["distance"] = target["distance"]

                jobs = scrape_jobs(**scrape_args)
                if jobs is not None and not jobs.empty:
                    all_jobs.append(jobs)
            except Exception as e:
                print(f"Error scraping query '{query}' in '{loc_str}': {e}")

    if not all_jobs:
        print("No jobs found across current Canadian search passes.")
        return

    combined_jobs = pd.concat(all_jobs, ignore_index=True)
    combined_jobs = combined_jobs.drop_duplicates(subset=['job_url'])

    required_student_keywords = [
        "intern", "internship", "interns", 
        "co-op", "coop", "cooperative", 
        "student", "placement", "fellow", "fellowship"
    ]

    required_science_keywords = [
        "bio", "chem", "lab", "laboratory", "research", "clinical", 
        "pharma", "genom", "molecular", "cell", "micro", "path", 
        "immun", "toxic", "scientific", "health", 
        "environ", "assay", "formulation", "medical", "neuro",
        "oncology", "drug", "medicine", "therapeut", "epidemiol",
        "pharmacokinet", "pharmacodynam", "biostatist"
    ]

    blacklist_terms = [
        "software", "hardware", "mechanical", "electrical", "civil", "structural", 
        "wireless", "rf", "antenna", "aerospace", "drone", "robotics", "full stack", 
        "frontend", "backend", "devops", "nursing", "registered nurse", "physician", 
        "accountant", "sales", "senior", "manager", "director", "lead",
        "ai", "ml", "machine learning", "artificial intelligence", "computer science",
        "developer", "data engineer", "data scientist"
    ]

    valid_jobs = []

    for _, row in combined_jobs.iterrows():
        job_id = str(row.get('job_url'))
        title = str(row.get('title', '')).lower()
        description = str(row.get('description', '')).lower()

        if job_id in seen_jobs or job_id == 'nan' or not job_id:
            continue

        # Exclude reposted jobs (checks if "reposted" appears in title or description metadata)
        if "reposted" in title or "reposted" in description:
            continue

        if any(bad in title for bad in blacklist_terms):
            continue

        if not any(req in title for req in required_student_keywords):
            continue

        if not any(sci in title for sci in required_science_keywords):
            continue

        valid_jobs.append({
            'id': job_id,
            'title': row.get('title'),
            'company': row.get('company', 'Unknown Company'),
            'location': row.get('location', 'N/A'),
            'job_url': row.get('job_url')
        })

    company_groups = {}
    for job in valid_jobs:
        comp = job['company']
        if comp not in company_groups:
            company_groups[comp] = []
        company_groups[comp].append(job)

    for company, jobs_list in company_groups.items():
        print(f"Sending grouped alert for {company} ({len(jobs_list)} roles)...")
        send_discord_group(company, jobs_list)
        for job in jobs_list:
            seen_jobs.add(job['id'])
            new_jobs_count += 1

    save_seen_jobs(seen_jobs)
    print(f"=== SCRAPING COMPLETE. Sent {new_jobs_count} new filtered Canadian life/medical science alerts across {len(company_groups)} companies. ===")

if __name__ == "__main__":
    main()
