# database_builder.py
import sqlite3
import requests
import gzip
import json
import os
from datetime import datetime, timedelta

class MTGDatabase:
    def __init__(self, db_path='data/mtg_cards.sqlite'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        print(f"DEBUG: Database will be at: {os.path.abspath(self.db_path)}")
        
    def initialize(self):
        """Create database schema if it doesn't exist"""
        print(f"DEBUG: Current directory: {os.getcwd()}")
        print(f"DEBUG: Data folder exists: {os.path.exists(os.path.dirname(self.db_path))}")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        print(f"DEBUG: Creating/connecting to database at: {self.db_path}")
        
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Create cards table with ONLY what we need
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                name TEXT PRIMARY KEY,
                asciiName TEXT,
                colors TEXT,
                type TEXT,
                types TEXT,
                rarity TEXT,
                manaCost TEXT,
                hasFoil INTEGER,
                layout TEXT,
                last_updated TIMESTAMP
            )
        ''')
        
        # Create update tracking table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS updates (
                id INTEGER PRIMARY KEY,
                last_bulk_update TIMESTAMP,
                card_count INTEGER
            )
        ''')
        
        self.conn.commit()
        
    def needs_update(self):
        """Check if database needs updating (older than 7 days)"""
        self.cursor.execute('SELECT last_bulk_update FROM updates ORDER BY id DESC LIMIT 1')
        result = self.cursor.fetchone()
        
        if not result:
            return True  # Never updated
            
        last_update = datetime.fromisoformat(result[0])
        return datetime.now() - last_update > timedelta(days=7)
    
    def download_bulk_data(self):
        """Download Scryfall bulk data"""
        print("Fetching Scryfall bulk data info...")
        
        # Get bulk data information
        response = requests.get('https://api.scryfall.com/bulk-data')
        bulk_data = response.json()
        
        # Find the default cards endpoint
        for item in bulk_data['data']:
            if item['type'] == 'default_cards':
                download_url = item['download_uri']
                print(f"Downloading from: {download_url}")
                
                # Download the JSON file (it's not actually gzipped)
                response = requests.get(download_url, stream=True)
                
                # Save as regular JSON file
                temp_path = 'data/bulk_data.json'
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                return temp_path
        
        raise Exception("Could not find default cards bulk data")
    
    def process_bulk_data(self, json_path):
        """Process bulk data and update database"""
        print("Processing bulk data...")
        
        cards_processed = 0
        batch_size = 1000
        batch = []
        
        with open(json_path, 'r', encoding='utf-8') as f:
            import json
            data = json.load(f)
            
            for card_data in data:
                # Handle double-faced cards specially to get front face data
                layout = card_data.get('layout', '')
                name = card_data.get('name', '')
                
                # Initialize with default values
                type_line = card_data.get('type_line', '')
                colors = card_data.get('colors', [])
                mana_cost = card_data.get('mana_cost', '')
                
                # Special handling for double-faced cards
                if layout in ['transform', 'modal_dfc', 'reversible_card', 'adventure'] and 'card_faces' in card_data:
                    card_faces = card_data.get('card_faces', [])
                    if len(card_faces) >= 1:
                        # Get front face data
                        front_face = card_faces[0]
                        
                        # For transform/modal DFCs, use front face type and colors
                        if layout in ['transform', 'modal_dfc', 'reversible_card']:
                            type_line = front_face.get('type_line', type_line)
                            colors = front_face.get('colors', colors)
                            mana_cost = front_face.get('mana_cost', mana_cost)
                        # For adventure cards, they have special handling
                        elif layout == 'adventure':
                            # Adventure cards show both faces in type_line already
                            # But we need to check colors from both faces
                            all_colors = set()
                            for face in card_faces:
                                face_colors = face.get('colors', [])
                                all_colors.update(face_colors)
                            colors = list(all_colors)
                
                types_array = self.extract_types_from_type_line(type_line)
                
                # Extract only the fields we need
                card_entry = (
                    name,
                    card_data.get('ascii_name', ''),
                    json.dumps(colors),  # Use corrected colors
                    type_line,
                    json.dumps(types_array),
                    card_data.get('rarity', ''),
                    mana_cost,  # Use corrected mana cost
                    1 if card_data.get('foil', False) or card_data.get('nonfoil', False) else 0,
                    layout,
                    datetime.now().isoformat()
                )
                
                batch.append(card_entry)
                
                if len(batch) >= batch_size:
                    self.insert_batch(batch)
                    cards_processed += len(batch)
                    print(f"Processed {cards_processed} cards...")
                    batch = []
        
        # Insert remaining cards
        if batch:
            self.insert_batch(batch)
            cards_processed += len(batch)
        
        # Update tracking
        self.cursor.execute('''
            INSERT INTO updates (last_bulk_update, card_count)
            VALUES (?, ?)
        ''', (datetime.now().isoformat(), cards_processed))
        
        self.conn.commit()
        print(f"Database updated! Total cards: {cards_processed}")
        
        # Clean up
        os.remove(json_path)
    
    def extract_types_from_type_line(self, type_line):
        """Extract card types from type line like 'Creature — Elf Warrior'"""
        if not type_line:
            return []
        
        # For double-faced cards, take only the first face
        if ' // ' in type_line:
            type_line = type_line.split(' // ')[0]
        
        # Remove everything after dash (for subtypes)
        type_part = type_line.split(' — ')[0]
        
        # Split by space and filter
        possible_types = ['Land', 'Creature', 'Artifact', 'Enchantment', 
                          'Instant', 'Sorcery', 'Planeswalker', 'Battle', 
                          'Token', 'Emblem', 'Scheme', 'Conspiracy', 
                          'Phenomenon', 'Vanguard', 'Hero']
        
        found_types = []
        for card_type in possible_types:
            if card_type in type_part:
                found_types.append(card_type)
        
        return found_types
    
    def insert_batch(self, batch):
        """Insert a batch of cards (upsert to handle updates)"""
        self.cursor.executemany('''
            INSERT OR REPLACE INTO cards 
            (name, asciiName, colors, type, types, rarity, manaCost, hasFoil, layout, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', batch)
    
    def build_or_update(self):
        """Main method to build or update database"""
        print("Initializing MTG card database...")
        self.initialize()
        
        if self.needs_update():
            print("Database is out of date, updating...")
            try:
                json_path = self.download_bulk_data()
                self.process_bulk_data(json_path)
                print("Database update complete!")
            except Exception as e:
                print(f"Update failed: {e}")
                print("Using existing database...")
        else:
            print("Database is up to date.")
        
        return self.conn
    
    

# Helper function for your app
def get_database_connection():
    """Get database connection, building/updating if needed"""
    db = MTGDatabase()
    return db.build_or_update()
    
if __name__ == "__main__":
    print("=== STARTING MTG DATABASE BUILDER ===")
    db = MTGDatabase()
    db.build_or_update()
    print("=== DATABASE BUILDER FINISHED ===")