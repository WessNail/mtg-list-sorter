from flask import Flask, request, jsonify
import sqlite3
import re
import os
import json
import sqlite3
import os
from database_builder import get_database_connection

app = Flask(__name__)

# HTML template with PROPER indentation
HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>MTG List Sorter</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 40px; 
            background: #f5f5f5; 
        }
        .container { 
            max-width: 1000px; 
            margin: 0 auto; 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        textarea { 
            width: 100%; 
            height: 300px; 
            padding: 10px; 
            font-size: 14px; 
            border: 2px solid #ddd; 
            border-radius: 5px; 
        }
        button { 
            padding: 12px 24px; 
            font-size: 16px; 
            background: #4CAF50; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
            margin: 10px 5px; 
        }
        button:hover { 
            background: #45a049; 
        }
        .btn-clear { 
            background: #f44336; 
        }
        .btn-clear:hover { 
            background: #d32f2f; 
        }
        .results { 
            margin-top: 30px; 
        }
        .card-item { 
            padding: 8px 10px; 
            border-bottom: 1px solid #eee; 
        }
        .card-item strong { 
            cursor: pointer; 
            display: inline-block; 
            padding: 2px 4px; 
            border-radius: 3px; 
            transition: background-color 0.2s; 
        }
        .card-item strong:hover { 
            background-color: #f0f0f0; 
        }
        .group-header { 
            background: #e3f2fd; 
            padding: 10px; 
            margin: 20px 0 10px 0; 
            border-radius: 5px; 
            font-weight: bold; 
        }
        .color-header { 
            background: #f5f5f5; 
            padding: 8px 10px; 
            margin: 15px 0 5px 0; 
            border-left: 4px solid #4CAF50; 
        }
        .not-found { 
            color: #f44336; 
            background: #ffebee; 
            padding: 10px; 
            border-radius: 5px; 
            margin: 10px 0; 
        }
        /* Remove any lingering tooltips */
        #card-image-tooltip ~ #card-image-tooltip {
            display: none !important;
        }
        .card-item {
            padding: 8px 10px 8px 30px; /* Increased left padding for quantity */
            border-bottom: 1px solid #eee;
            position: relative; /* For absolute positioning of quantity */
            min-height: 24px; /* Ensure consistent height */
        }

        .card-quantity {
            position: absolute;
            left: 8px;
            top: 50%;
            transform: translateY(-50%);
            width: 20px;
            text-align: right;
            font-weight: bold;
            color: #666;
            font-size: 0.9em;
        }

        .card-item strong {
            cursor: pointer;
            display: inline-block;
            padding: 2px 4px;
            border-radius: 3px;
            transition: background-color 0.2s;
            margin-left: 4px; /* Space after quantity */
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🃏 MTG List Sorter</h1>
        <p>Paste your card list (one per line, can include quantities like "4x Lightning Bolt"):</p>
        
        <textarea id="cardInput" placeholder="Example:
4x Lightning Bolt
2x Counterspell
1x Sol Ring
Black Lotus
Island
Swamp
Mountain
Forest
Plains"></textarea>
        
        <div>
            <button onclick="processList()">Sort & Group Cards</button>
            <button class="btn-clear" onclick="clearList()">Clear</button>
        </div>
        
        <div id="message"></div>
        <div id="results"></div>
    </div>

    <script>
async function processList() {
    const cardText = document.getElementById('cardInput').value;
    if (!cardText.trim()) {
        showMessage('Please paste some card names!', 'error');
        return;
    }
    
    const lines = cardText.trim().split('\\n');
    let cardCount = 0;
    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.length > 0 && !trimmed.startsWith('#')) {
            cardCount++;
        }
    }
    
    const minTime = Math.ceil(cardCount / 50);
    const maxTime = Math.ceil(cardCount / 20);
    
    const processBtn = document.querySelector('button[onclick="processList()"]');
    const originalText = processBtn.textContent;
    processBtn.textContent = 'Processing...';
    processBtn.disabled = true;
    
    document.getElementById('message').innerHTML = '';
    
    document.getElementById('results').innerHTML = 
        '<div class="progress-container" style="margin: 20px 0; text-align: center;">' +
        '<div class="spinner" style="border: 5px solid #f3f3f3; border-top: 5px solid #4CAF50; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 0 auto;"></div>' +
        '<style>@keyframes spin {0% { transform: rotate(0deg); }100% { transform: rotate(360deg); }}</style>' +
        '<div id="progressText" style="margin-top: 15px; color: #666;">Looking up ' + cardCount + ' cards... This may take a moment.</div>' +
        '</div>';
    
    try {
        const response = await fetch('/process_list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cards: cardText })
        });
        
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('Non-JSON response:', text.substring(0, 200));
            throw new Error('Server returned HTML instead of JSON. Check server logs.');
        }
        
        const result = await response.json();
        
        if (result.error) {
            showMessage('Error: ' + result.error, 'error');
            return;
        }
        
        displayResults(result);
        showMessage('✅ Processed ' + result.total_cards + ' card entries (representing ' + result.total_cards_input + ' total cards) successfully!', 'success');
        
    } catch (error) {
        showMessage('Error: ' + error.message, 'error');
        console.error('Full error:', error);
    } finally {
        processBtn.textContent = originalText;
        processBtn.disabled = false;
    }
}

function displayResults(result) {
    let html = '<h2>Results (' + result.total_cards + ' card entries, ' + result.total_cards_input + ' total cards)</h2>';
    
    if (result.total_not_found > 0) {
        html += '<div class="not-found"><h3>❌ Not Found (' + result.total_not_found + '):</h3><ul>';
        result.not_found.forEach(card => {
            html += '<li>' + card + '</li>';
        });
        html += '</ul></div>';
    }
    
    const groups = result.grouped || {};
    const rarityOrder = ['Mythic/Rare', 'Common/Uncommon'];
    const colorOrder = ['White', 'Blue', 'Black', 'Red', 'Green', 
                       'Multicolor', 'Colorless', 'Artifact', 'Land', 
                       'Special Cards', 'Unknown'];
    
    for (const rarity of rarityOrder) {
        if (groups[rarity]) {
            html += '<div class="group-header">' + rarity + '</div>';
            
            for (const color of colorOrder) {
                if (groups[rarity][color]) {
                    const cards = groups[rarity][color];
                    html += '<div class="color-header">' + color + ' (' + cards.length + ' cards)</div>';
                    
                    cards.forEach(card => {
                        html += '<div class="card-item">';
                        
                        // Add quantity display if > 1
                        if (card.quantity && card.quantity > 1) {
                            html += '<span class="card-quantity">' + card.quantity + '×</span> ';
                        } else {
                            html += '<span class="card-quantity"></span> ';
                        }
                        
                        html += '<strong>' + card.name + '</strong>';
                        html += '</div>';
                    });
                }
            }
        }
    }
    
    document.getElementById('results').innerHTML = html;
    
    // Enable card image hover for new results
    setTimeout(() => {
        if (typeof CardImageHover !== 'undefined') {
            CardImageHover.attachToResults();
        }
    }, 100);
}

function showMessage(text, type) {
    const colors = {
        'error': '#f44336',
        'success': '#4CAF50', 
        'info': '#2196F3'
    };
    document.getElementById('message').innerHTML = 
        '<div style="background: ' + (colors[type] || '#2196F3') + '; color: white; padding: 10px; border-radius: 5px; margin: 10px 0;">' +
        text +
        '</div>';
}

function clearList() {
    document.getElementById('cardInput').value = '';
    document.getElementById('results').innerHTML = '';
    document.getElementById('message').innerHTML = '';
}

document.getElementById('cardInput').addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        processList();
    }
});

// ======================
// CARD IMAGE HOVER MODULE (WITH QUANTITY SUPPORT)
// ======================
const CardImageHover = {
    cache: new Map(),
    hoverDelay: 500,
    hideDelay: 100,
    currentHover: null,
    hoverTimeout: null,
    hideTimeout: null,
    fadeOutTimeout: null,
    currentTooltip: null,
    
    init() {
        // Listen for mouseover on CARD NAME TEXT OR QUANTITY
        document.addEventListener('mouseover', (e) => {
            // Check if hovering over card name text OR quantity
            const cardNameElement = e.target.closest('strong');
            const quantityElement = e.target.closest('.card-quantity');
            
            if ((cardNameElement || quantityElement) && e.target.closest('.card-item')) {
                const cardItem = e.target.closest('.card-item');
                this.handleCardHover(cardItem, e);
            }
        });
        
        // Listen for mouseleave on the TEXT or QUANTITY
        document.addEventListener('mouseout', (e) => {
            // Check if we're leaving a card name text or quantity element
            if ((e.target.tagName === 'STRONG' || e.target.classList.contains('card-quantity')) && 
                e.target.closest('.card-item')) {
                
                // Check if we're moving to a NON-text/non-quantity element
                const related = e.relatedTarget;
                
                // If moving to something that's NOT strong text or quantity, OR not within same card
                if (!related || 
                    (!related.closest('strong') && !related.closest('.card-quantity')) || 
                    related.closest('.card-item') !== e.target.closest('.card-item')) {
                    
                    // LEAVING TEXT/QUANTITY AREA - hide immediately
                    this.handleCardLeave();
                }
            }
        });
        
        // Also hide if clicking anywhere on page (safety)
        document.addEventListener('click', () => {
            this.hideCardImageImmediately();
        });
    },
    
    handleCardHover(cardItem, event) {
        clearTimeout(this.hideTimeout);
        clearTimeout(this.fadeOutTimeout);
        
        // Get card name from strong element (skip quantity)
        const cardNameElement = cardItem.querySelector('strong');
        if (!cardNameElement) return;
        
        let cardName = cardNameElement.textContent;
        cardName = cardName.replace(/\s*\(FOIL.*\)/, '').trim();
        
        this.currentHover = cardName;
        
        this.hoverTimeout = setTimeout(() => {
            this.fetchAndDisplayCardImage(cardName, event);
        }, this.hoverDelay);
    },
    
    handleCardLeave() {
        clearTimeout(this.hoverTimeout);
        this.currentHover = null;
        
        // Hide immediately - no delay when leaving text/quantity
        this.hideCardImageImmediately();
    },
    
    async fetchAndDisplayCardImage(cardName, event) {
        if (this.cache.has(cardName)) {
            const cached = this.cache.get(cardName);
            if (cached === null) return;
            this.displayCardImage(cached, event);
            return;
        }
        
        try {
            const encodedName = encodeURIComponent(cardName);
            const response = await fetch(`https://api.scryfall.com/cards/named?fuzzy=${encodedName}`);
            
            if (!response.ok) {
                this.cache.set(cardName, null);
                return;
            }
            
            const cardData = await response.json();
            
            if (!this.hasAnyImage(cardData)) {
                this.cache.set(cardName, null);
                return;
            }
            
            this.cache.set(cardName, cardData);
            
            if (this.currentHover === cardName) {
                this.displayCardImage(cardData, event);
            }
            
        } catch (error) {
            console.error(`Fetch error:`, error);
            this.cache.set(cardName, null);
        }
    },
    
    hasAnyImage(cardData) {
        if (cardData.image_uris && (cardData.image_uris.normal || cardData.image_uris.large || cardData.image_uris.small)) {
            return true;
        }
        
        if (cardData.card_faces && cardData.card_faces.length > 0) {
            return cardData.card_faces.some(face => 
                face.image_uris && (face.image_uris.normal || face.image_uris.large || face.image_uris.small)
            );
        }
        
        return false;
    },
    
    getImageUrl(cardData) {
        if (cardData.layout === "adventure" && cardData.image_uris) {
            return cardData.image_uris.normal || cardData.image_uris.large || cardData.image_uris.small;
        }
        
        if (cardData.image_uris && (cardData.image_uris.normal || cardData.image_uris.large || cardData.image_uris.small)) {
            return cardData.image_uris.normal || cardData.image_uris.large || cardData.image_uris.small;
        }
        
        if (cardData.card_faces && cardData.card_faces.length > 0) {
            const firstFace = cardData.card_faces[0];
            if (firstFace.image_uris) {
                return firstFace.image_uris.normal || firstFace.image_uris.large || firstFace.image_uris.small;
            }
        }
        
        return null;
    },
    
    displayCardImage(cardData, event) {
        // Remove ALL existing tooltips
        document.querySelectorAll('#card-image-tooltip').forEach(tooltip => {
            if (tooltip.parentNode) tooltip.remove();
        });
        
        if (!cardData) return;
        
        const tooltip = document.createElement('div');
        tooltip.id = 'card-image-tooltip';
        
        const imageUrl = this.getImageUrl(cardData);
        if (!imageUrl) return;
        
        const isDoubleFaced = cardData.card_faces && cardData.card_faces.length >= 2;
        const isAdventure = cardData.layout === "adventure";
        const showSideBySide = isDoubleFaced && !isAdventure;
        
        if (showSideBySide) {
            const validFaces = cardData.card_faces.filter(face => 
                face.image_uris && (face.image_uris.normal || face.image_uris.large || face.image_uris.small)
            );
            
            if (validFaces.length === 0) return;
            
            tooltip.style.cssText = `
                position: fixed;
                z-index: 10000;
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                padding: 10px;
                width: ${validFaces.length === 2 ? '640px' : '320px'};
                height: 480px;
                pointer-events: none;
                display: flex;
                gap: 10px;
                align-items: center;
                justify-content: center;
                opacity: 0;
                transition: opacity 0.15s ease-in-out;
            `;
            
            const facesContainer = document.createElement('div');
            facesContainer.style.cssText = `
                display: flex;
                gap: 10px;
                width: 100%;
                height: 100%;
            `;
            
            validFaces.forEach((face) => {
                const faceContainer = document.createElement('div');
                faceContainer.style.cssText = `
                    flex: 1;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                `;
                
                const faceImageUrl = face.image_uris.normal || face.image_uris.large || face.image_uris.small;
                const img = document.createElement('img');
                img.src = faceImageUrl;
                img.style.cssText = `
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                    border-radius: 4px;
                `;
                img.alt = face.name;
                
                faceContainer.appendChild(img);
                facesContainer.appendChild(faceContainer);
            });
            
            tooltip.appendChild(facesContainer);
            
        } else {
            tooltip.style.cssText = `
                position: fixed;
                z-index: 10000;
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                padding: 10px;
                width: 320px;
                height: 445px;
                pointer-events: none;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                transition: opacity 0.15s ease-in-out;
            `;
            
            const img = document.createElement('img');
            img.src = imageUrl;
            img.style.cssText = `
                width: 100%;
                height: 100%;
                object-fit: contain;
                border-radius: 4px;
            `;
            img.alt = cardData.name;
            
            tooltip.appendChild(img);
        }
        
        document.body.appendChild(tooltip);
        this.positionTooltip(tooltip, event, showSideBySide);
        
        // Fade in
        setTimeout(() => {
            if (tooltip.parentNode && this.currentHover) {
                tooltip.style.opacity = '1';
            } else if (tooltip.parentNode) {
                tooltip.remove();
            }
        }, 10);
        
        // Update position while hovering
        const updatePosition = (e) => {
            if (this.currentHover && tooltip.parentNode) {
                this.positionTooltip(tooltip, e, showSideBySide);
            }
        };
        
        document.addEventListener('mousemove', updatePosition);
        
        this.currentTooltip = { 
            element: tooltip, 
            updatePosition,
            isWide: showSideBySide 
        };
    },
    
    positionTooltip(tooltip, mouseEvent, isWide) {
        if (!mouseEvent || !tooltip.parentNode) return;
        
        const mouseX = mouseEvent.clientX;
        const mouseY = mouseEvent.clientY;
        const tooltipWidth = isWide ? 640 : 320;
        const tooltipHeight = isWide ? 480 : 445;
        const padding = 20;
        
        let left = mouseX + padding;
        let top = mouseY + padding;
        
        if (left + tooltipWidth > window.innerWidth) {
            left = mouseX - tooltipWidth - padding;
        }
        
        if (top + tooltipHeight > window.innerHeight) {
            top = mouseY - tooltipHeight - padding;
        }
        
        const minMargin = 10;
        left = Math.max(minMargin, Math.min(left, window.innerWidth - tooltipWidth - minMargin));
        top = Math.max(minMargin, Math.min(top, window.innerHeight - tooltipHeight - minMargin));
        
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    },
    
    hideCardImageImmediately() {
        clearTimeout(this.fadeOutTimeout);
        
        if (this.currentTooltip) {
            document.removeEventListener('mousemove', this.currentTooltip.updatePosition);
            
            if (this.currentTooltip.element && this.currentTooltip.element.parentNode) {
                this.currentTooltip.element.remove();
            }
            
            this.currentTooltip = null;
        }
        
        // Also remove any stray tooltips
        document.querySelectorAll('#card-image-tooltip').forEach(tooltip => {
            if (tooltip.parentNode) tooltip.remove();
        });
    },
    
    attachToResults() {
        this.init();
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    CardImageHover.init();
});

    </script>
</body>
</html>'''

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/process_list', methods=['POST'])
def process_list():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        card_text = data.get('cards', '')
        if not card_text:
            return jsonify({'error': 'No cards provided'}), 400
        
        print(f"Processing request")
        
        card_entries = []
        not_found = []
        
        for line in card_text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            quantity_match = re.match(r'^(\d+)\s*x?\s*', line)
            quantity = 1
            if quantity_match:
                quantity = int(quantity_match.group(1))
                line = line[quantity_match.end():].strip()
            
            foil = False
            foil_pattern = r'(?i)\s*(?:\(?foil\)?|\*)\s*$'
            if re.search(foil_pattern, line):
                foil = True
                line = re.sub(foil_pattern, '', line).strip()
            
            line = line.strip()
            if line:
                card_entries.append({
                    'name': line,
                    'quantity': quantity,
                    'foil': foil
                })
        
        print(f"Processing {len(card_entries)} card entries")
        
        # Get database connection (auto-builds/updates if needed)
        try:
            conn = get_database_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
        except Exception as e:
            print(f"Database error: {e}")
            # Fallback option: you could implement Scryfall API fallback here
            return jsonify({
                'error': 'Card database unavailable. Please try again later.'
            }), 500
        
        groups = {
            'Mythic/Rare': {},
            'Common/Uncommon': {}
        }
        
        color_order = ['White', 'Blue', 'Black', 'Red', 'Green', 
                      'Multicolor', 'Colorless', 'Artifact', 'Land', 
                      'Special Cards', 'Unknown']
        
        for rarity in groups:
            for color in color_order:
                groups[rarity][color] = []
        
        for entry in card_entries:
            card_name = entry['name']
            
            try:
                # Find the card, but prefer front face entries for double-faced cards
                cursor.execute("""
                    SELECT name, asciiName, colors, type, types, rarity, manaCost, hasFoil
                    FROM cards 
                    WHERE (LOWER(asciiName) = LOWER(?)
                           OR LOWER(name) = LOWER(?))
                    ORDER BY 
                        -- CRITICAL: Prefer entries where Land is NOT in types array
                        -- (This puts front face entries first for double-faced cards)
                        CASE 
                            WHEN types LIKE '%"Land"%' THEN 2
                            ELSE 1
                        END
                    LIMIT 1
                """, (card_name, card_name))
                
                result = cursor.fetchone()
                
                # Fallback for double-faced front names
                if not result and ' // ' not in card_name:
                    cursor.execute("""
                        SELECT name, asciiName, colors, type, types, rarity, manaCost, hasFoil
                        FROM cards 
                        WHERE (name LIKE ? || ' //%'
                               OR asciiName LIKE ? || ' //%')
                        ORDER BY 
                            CASE 
                                WHEN types LIKE '%"Land"%' THEN 2
                                ELSE 1
                            END
                        LIMIT 1
                    """, (card_name, card_name))
                    result = cursor.fetchone()
                
                if not result:
                    not_found.append(card_name)
                    continue
                
                # Clean up self-meld cards
                db_name = result['name']
                if ' // ' in db_name:
                    parts = db_name.split(' // ')
                    if len(parts) == 2 and parts[0] == parts[1]:
                        clean_name = parts[0]
                        cursor.execute("""
                            SELECT name, asciiName, colors, type, types, rarity, manaCost, hasFoil
                            FROM cards 
                            WHERE (LOWER(asciiName) = LOWER(?)
                                   OR LOWER(name) = LOWER(?))
                                  AND name NOT LIKE '% // %'
                            LIMIT 1
                        """, (clean_name, clean_name))
                        
                        cleaner_result = cursor.fetchone()
                        if cleaner_result:
                            print(f"  Replaced self-meld '{db_name}' with '{cleaner_result['name']}'")
                            result = cleaner_result
                
                print(f"  Matched '{card_name}' -> '{result['name']}' (types: {result['types']})")
                    
            except sqlite3.OperationalError as e:
                print(f"SQL error for '{card_name}': {e}")
                not_found.append(card_name)
                continue
            
            try:
                colors = json.loads(result['colors']) if result['colors'] else []
            except:
                colors = []
            
            try:
                types = json.loads(result['types']) if result['types'] else []
            except:
                types = []
            
            rarity = result['rarity'].lower() if result['rarity'] else ''
            if rarity in ['mythic', 'rare']:
                rarity_group = 'Mythic/Rare'
            else:
                rarity_group = 'Common/Uncommon'
            
            # Color group - FIXED: Check front face only for double-faced cards
            color_group = 'Unknown'
            
            # For double-faced cards, extract just the front face name for analysis
            display_name = result['name']
            is_double_faced = ' // ' in display_name
            
            # Check mana cost for colors
            mana_colors = set()
            mana_cost = result['manaCost'] or ''
            if mana_cost:
                for symbol in ['W', 'U', 'B', 'R', 'G']:
                    if f'{{{symbol}}}' in mana_cost:
                        mana_colors.add(symbol)
            
            all_colors = set(colors) | mana_colors
            
            # Special Cards check (but NOT for double-faced cards' back faces)
            type_str = result['type'] or ''
            
            # IMPORTANT: For double-faced cards, only consider the FIRST type
            # Example: "Enchantment — Aura // Land" should be treated as Enchantment
            if is_double_faced and ' // ' in type_str:
                # Take only the front face type
                type_str = type_str.split(' // ')[0]
            
            # Lands WITHOUT colors (basic lands, etc.)
            # BUT: If it's a double-faced card where front is NOT a land, don't put in Land group
            if 'Land' in types and len(all_colors) == 0:
                # Check if this is actually a land (not a double-faced card with land back)
                if is_double_faced:
                    # Check if the FRONT face is a land
                    front_type = type_str.split(' // ')[0] if ' // ' in type_str else type_str
                    if 'Land' in front_type:
                        color_group = 'Land'
                    else:
                        # Double-faced card with non-land front, land back - group by front
                        pass  # Will be handled by normal color logic below
                else:
                    # Regular land
                    color_group = 'Land'
            
            # Special Cards (but not if they're regular cards)
            if color_group == 'Unknown':
                special_types = ["Token", "Emblem", "Scheme", "Conspiracy", 
                               "Phenomenon", "Vanguard", "Hero"]
                
                if any(special_type in type_str for special_type in special_types):
                    # Check if it's ALSO a regular card type
                    is_regular_card = any(regular_type in type_str for regular_type in 
                                         ["Creature", "Planeswalker", "Instant", "Sorcery", 
                                          "Enchantment", "Artifact", "Land", "Battle"])
                    
                    if not is_regular_card:
                        color_group = 'Special Cards'
            
            # If still unknown, determine by color
            if color_group == 'Unknown':
                # For double-faced cards, check if front is Artifact
                front_is_artifact = 'Artifact' in type_str.split(' // ')[0] if ' // ' in type_str else 'Artifact' in type_str
                
                # Colorless artifacts (no colors at all) AND front face is artifact
                if front_is_artifact and len(all_colors) == 0:
                    color_group = 'Artifact'
                # Single color
                elif len(all_colors) == 1:
                    color_map = {'W': 'White', 'U': 'Blue', 'B': 'Black', 'R': 'Red', 'G': 'Green'}
                    color_group = color_map.get(list(all_colors)[0], 'Unknown')
                # Multicolor
                elif len(all_colors) >= 2:
                    color_group = 'Multicolor'
                # Truly colorless (not artifact, not land)
                elif len(all_colors) == 0:
                    color_group = 'Colorless'
                else:
                    color_group = 'Unknown'
            
            display_name = result['name']
            if entry['foil']:
                if result['hasFoil'] == 1:
                    display_name = f"{result['name']} (FOIL)"
                else:
                    display_name = f"{result['name']} (FOIL*)"
            
            card_entry = {
                'name': display_name,
                'type_line': result['type'] or '',
                'mana_cost': result['manaCost'] or '',
                'color_group': color_group,
                'rarity_group': rarity_group,
                'foil': entry['foil'],
                'quantity': entry['quantity'],
                'sort_key': result['name'].lower()
            }
            
            # Store quantity in the card entry (NO duplicates)
            card_entry['quantity'] = entry['quantity']
            groups[rarity_group][color_group].append(card_entry)
        
        conn.close()
        
        # FIXED: Proper sorting logic
        for rarity in groups:
            for color in groups[rarity]:
                # Sort by name (alphabetical), then by foil (non-foil first)
                groups[rarity][color].sort(key=lambda x: (x['sort_key'], x['foil']))
                for card in groups[rarity][color]:
                    if 'sort_key' in card:
                        del card['sort_key']
        
        for rarity in list(groups.keys()):
            for color in list(groups[rarity].keys()):
                if not groups[rarity][color]:
                    del groups[rarity][color]
        
        total_cards_input = sum(entry['quantity'] for entry in card_entries)
        total_cards_found = sum(len(cards) for rarity in groups.values() 
                               for cards in rarity.values())
        
        response = {
            'grouped': groups,
            'not_found': not_found,
            'total_cards': total_cards_found,
            'total_cards_input': total_cards_input,
            'total_not_found': len(not_found)
        }
        
        print(f"Processed {total_cards_found} of {total_cards_input} cards, {len(not_found)} not found")
        return jsonify(response)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

# This runs when Render STARTS the app (not when users visit)
print("🚀 Render is starting up...")

# Build database if it doesn't exist
db_path = 'data/mtg_cards.sqlite'
if not os.path.exists(db_path):
    print("📦 No database found. Building now...")
    from database_builder import MTGDatabase
    db = MTGDatabase()
    db.build_or_update()
    print("✅ Database ready!")
else:
    print("✅ Database already exists!")

if __name__ == '__main__':
    os.makedirs('data', exist_ok=True)
    
    print("=" * 50)
    print("MTG List Sorter - REAL DATABASE MODE")
    print("=" * 50)
    print("\n🚀 Starting server...")
    print("👉 Open: http://localhost:5000")
    print("👉 Press Ctrl+C to stop")
    print("=" * 50)
    
    app.run(debug=True, port=5000, host='0.0.0.0')