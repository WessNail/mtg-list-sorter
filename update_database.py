# update_database.py - Simple script for GitHub Actions
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_builder import MTGDatabase
from datetime import datetime

def main():
    print(f"{datetime.now()}: Starting database update...")
    
    try:
        # Create/update database
        db = MTGDatabase('data/mtg_cards.sqlite')
        db.initialize()
        
        # Always update in GitHub Actions (fresh each time)
        print("Downloading latest card data from Scryfall...")
        gzip_path = db.download_bulk_data()
        db.process_bulk_data(gzip_path)
        
        print(f"{datetime.now()}: Database update complete!")
        return True
        
    except Exception as e:
        print(f"Error updating database: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)