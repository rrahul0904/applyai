from datetime import datetime, timedelta, timezone


CATEGORIES = [
    ("Software", ["Software Engineer", "Platform Engineer"]),
    ("Data", ["Data Analyst", "Analytics Engineer"]),
    ("AI/ML", ["Machine Learning Engineer", "Applied AI Scientist"]),
    ("Healthcare", ["Registered Nurse", "Clinical Operations Manager"]),
    ("Research", ["Research Associate", "Research Program Manager"]),
    ("Finance", ["Financial Analyst", "Finance Manager"]),
    ("Accounting", ["Staff Accountant", "Accounting Manager"]),
    ("Marketing", ["Growth Marketing Manager", "Content Strategist"]),
    ("Sales", ["Account Executive", "Sales Operations Manager"]),
    ("Operations", ["Operations Manager", "Business Operations Analyst"]),
    ("Human Resources", ["People Operations Partner", "Talent Acquisition Specialist"]),
    ("Customer Support", ["Customer Success Manager", "Support Operations Lead"]),
    ("Product", ["Product Manager", "Product Operations Manager"]),
    ("Design", ["Product Designer", "Design Systems Lead"]),
    ("Education", ["Instructional Designer", "Academic Program Manager"]),
    ("Supply Chain", ["Supply Chain Analyst", "Logistics Manager"]),
    ("Project Management", ["Project Manager", "Technical Program Manager"]),
    ("Clinical Research", ["Clinical Research Coordinator", "Clinical Trial Manager"]),
]

COMPANIES = [
    "Northstar Health",
    "Brightline Learning",
    "Cedar Ridge Finance",
    "Harborfield Labs",
    "Juniper Works",
    "Mosaic Supply",
    "Orchard Systems",
    "Pioneer Care",
    "Riverstone Research",
    "Summit Customer Co.",
    "Tandem Market",
    "Willow Operations",
]

LOCATIONS = [
    ("Boston, MA", "HYBRID"),
    ("New York, NY", "ONSITE"),
    ("Chicago, IL", "HYBRID"),
    ("Austin, TX", "ONSITE"),
    ("Denver, CO", "REMOTE"),
    ("Seattle, WA", "HYBRID"),
    ("Remote — United States", "REMOTE"),
    ("Atlanta, GA", "ONSITE"),
]

SKILLS = {
    "Software": ["TypeScript", "Python", "APIs", "Cloud infrastructure"],
    "Data": ["SQL", "Analytics", "Data visualization", "Experimentation"],
    "AI/ML": ["Python", "Machine learning", "Model evaluation", "MLOps"],
    "Healthcare": ["Patient care", "Clinical workflows", "Care coordination"],
    "Research": ["Research methods", "Analysis", "Technical writing"],
    "Finance": ["Financial modeling", "Forecasting", "Excel", "Reporting"],
    "Accounting": ["GAAP", "Reconciliation", "Month-end close"],
    "Marketing": ["Campaign strategy", "Analytics", "Content"],
    "Sales": ["Pipeline management", "CRM", "Forecasting"],
    "Operations": ["Process improvement", "Analytics", "Program management"],
    "Human Resources": ["Recruiting", "Employee relations", "HRIS"],
    "Customer Support": ["Customer success", "Escalation management", "CRM"],
    "Product": ["Product strategy", "Roadmapping", "User research", "Analytics"],
    "Design": ["Figma", "Interaction design", "Design systems"],
    "Education": ["Curriculum design", "Learning systems", "Facilitation"],
    "Supply Chain": ["Inventory planning", "Logistics", "ERP"],
    "Project Management": ["Project planning", "Stakeholder management", "Risk management"],
    "Clinical Research": ["GCP", "Clinical trials", "Regulatory documentation"],
}


def build_seed_records() -> list[dict]:
    records: list[dict] = []
    base_time = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    for category_index, (category, titles) in enumerate(CATEGORIES):
        for role_index in range(8):
            title = titles[role_index % len(titles)]
            company = COMPANIES[(category_index + role_index) % len(COMPANIES)]
            location, work_mode = LOCATIONS[(category_index * 2 + role_index) % len(LOCATIONS)]
            skills = SKILLS[category]
            seniority = ["ENTRY", "MID", "SENIOR", "MANAGER"][role_index % 4]
            salary_floor = 52000 + category_index * 2400 + role_index * 3500
            records.append(
                {
                    "external_job_id": f"dev-{category_index:02d}-{role_index:02d}",
                    "company_name": company,
                    "title": title,
                    "description": (
                        f"{company} is hiring a {title} to improve meaningful outcomes "
                        f"across its {category.lower()} organization. This fictional "
                        "development posting is designed to exercise ApplyAI search, "
                        "filtering, saving, and application tracking."
                    ),
                    "application_url": (
                        f"https://jobs.applyai.test/{category_index:02d}/{role_index:02d}"
                    ),
                    "locations": [location],
                    "work_mode": work_mode,
                    "employment_type": "FULL_TIME" if role_index != 7 else "CONTRACT",
                    "seniority": seniority,
                    "salary_min": salary_floor,
                    "salary_max": salary_floor + 28000,
                    "salary_provenance": "DEVELOPMENT_DATA",
                    "skills": skills[: 3 + (role_index % 2)],
                    "requirements": [
                        f"Demonstrated experience in {skills[0]}",
                        "Clear written and verbal communication",
                        "Ability to work with cross-functional partners",
                    ],
                    "posted_at": (base_time - timedelta(days=role_index * 3)).isoformat(),
                    "data_origin": "DEVELOPMENT_SEED",
                }
            )
    return records
