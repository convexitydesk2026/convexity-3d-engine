import sqlite3
import os

DB_PATH = "estate_data.db"

def scrub_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Fetch all campaigns that have tags
    c.execute("SELECT id, tags FROM alpha_campaigns WHERE tags IS NOT NULL")
    rows = c.fetchall()

    # Keywords that identify a machine-generated tag
    math_keywords = ['SMA', 'Regime', 'Sector_', 'Long', 'Short']
    updated_count = 0

    for row_id, tags in rows:
        cleaned_tags = []
        # Split the comma-separated string
        for t in tags.split(','):
            t = t.strip()
            # Keep the tag ONLY if it does not contain a math keyword
            if not any(kw in t for kw in math_keywords) and t:
                cleaned_tags.append(t)
        
        new_tag_str = ", ".join(cleaned_tags)
        
        # Update the database if the tags were changed
        if new_tag_str != tags:
            c.execute("UPDATE alpha_campaigns SET tags = ? WHERE id = ?", (new_tag_str, row_id))
            updated_count += 1

    # 2. Delete the current Glossary table entirely
    c.execute("DELETE FROM tag_glossary")

    conn.commit()
    conn.close()
    print(f"Success! Scrubbed math tags from {updated_count} campaigns and flushed the Glossary.")

if __name__ == "__main__":
    scrub_database()