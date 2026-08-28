import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_skills_gap_detects_known_skill():
    jd_text = "Looking for someone with strong Kafka and dbt experience."
    jd_lower = jd_text.lower()
    SKILLS = ["Python", "SQL", "dbt", "Airflow", "Kafka", "Spark", "Databricks"]
    relevant = [s for s in SKILLS if s.lower() in jd_lower]
    assert "Kafka" in relevant
    assert "dbt" in relevant
    assert "Python" not in relevant

def test_skills_gap_handles_no_matches():
    jd_text = "Looking for a marketing coordinator."
    SKILLS = ["Python", "SQL", "dbt", "Airflow", "Kafka"]
    jd_lower = jd_text.lower()
    relevant = [s for s in SKILLS if s.lower() in jd_lower]
    assert relevant == []