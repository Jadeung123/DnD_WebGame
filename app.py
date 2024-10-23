from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import random
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai
from dotenv import load_dotenv
import re
import pyttsx3
import requests
import uuid

MAX_TEXT_LENGTH = 300
MAX_LOG_SIZE = 3

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

DICE = {
    "D4": (4, "Four-sided dice"),
    "D6": (6, "Six-sided dice"),
    "D8": (8, "Eight-sided dice"),
    "D10": (10, "Ten-sided dice"),
    "D12": (12, "Twelve-sided dice"),
    "D20": (20, "Twenty-sided dice")
}

RACES = {
    "Human": "Versatile and adaptable. +1 to all stats.",
    "Elf": "Graceful and perceptive. +2 Dexterity, +1 Wisdom.",
    "Dwarf": "Tough and resilient. +2 Constitution, +2 Strength.",
    "Halfling": "Lucky and brave. +2 Dexterity.",
    "Half-Orc": "Strong and fierce. +2 Strength, +1 Constitution.",
    "Half-Elf": "Charismatic and adaptable. +2 Charisma, +1 to two other stats.",
    "Gnome": "Inventive and cunning. +2 Intelligence.",
    "Tiefling": "Mysterious and charismatic. +2 Charisma, +1 Intelligence.",
    "Dragonborn": "Proud and draconic. +2 Strength, +1 Charisma.",
    "Aasimar": "Celestial protectors. +2 Charisma, +1 Wisdom.",
    "Goliath": "Strong and enduring. +2 Strength, +1 Constitution.",
    "Firbolg": "Gentle and nature-loving. +2 Wisdom, +1 Strength.",
    "Kenku": "Mimics and stealthy. +2 Dexterity, +1 Wisdom.",
    "Tabaxi": "Curious and agile. +2 Dexterity, +1 Charisma.",
    "Triton": "Guardians of the deep. +1 Strength, Constitution, Charisma.",
    "Lizardfolk": "Survivors and practical. +2 Constitution, +1 Wisdom.",
    "Genasi": "Elemental heritage. +2 Constitution.",
    "Warforged": "Tireless and adaptable. +2 Constitution, +1 to one other stat.",
    "Changeling": "Shapechangers and cunning. +2 Charisma, +1 to another stat.",
    "Kalashtar": "Mystical and wise. +2 Wisdom, +1 Charisma.",
    "Yuan-ti Pureblood": "Serpentine and devious. +2 Charisma, +1 Intelligence.",
    "Gith": "Disciplined and skilled. +2 Intelligence, +1 Dexterity."
}

STATS_ORDER = ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 300,
    "response_mime_type": "text/plain",
}

# def generate_tts_for_scenario(scenario_text):
#     """Generate TTS audio for the given scenario and create a unique filename."""
#     engine = pyttsx3.init()
#     unique_filename = f"tts_audio_{uuid.uuid4()}.mp3"
#     audio_file_path = os.path.join('static', unique_filename)

#     # Convert the file path to use forward slashes (for URLs)
#     audio_file_path = audio_file_path.replace('\\', '/')

#     engine.save_to_file(scenario_text, audio_file_path)
#     engine.runAndWait()

#     return unique_filename  # Return just the filename, not the full path

def search_character_image(name, race, lore):
    """Search for a character image using Pexels API."""
    api_key = os.getenv("PEXELS_API_KEY")
    url = "https://api.pexels.com/v1/search"
    headers = {
        "Authorization": api_key
    }
    query = f"{race} fantasy {name} {lore}"
    params = {
        "query": query,
        "per_page": 1
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        result = response.json()
        image_url = result['photos'][0]['src']['original']
        return image_url
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

@app.route('/generate_profile', methods=['POST'])
def generate_profile():
    """Generate the character profile image and save to session."""
    name = request.form['name']
    surname = request.form['surname']
    race = request.form['race']
    lore = request.form['lore']

    session['name'] = name
    session['surname'] = surname
    session['race'] = race
    session['lore'] = lore

    character_image_url = search_character_image(name, race, lore)

    if character_image_url:
        session['character_image'] = character_image_url
        session.modified = True

    return render_template(
        'customize_character.html',
        races=RACES,
        character_image=character_image_url,
        profile_generated=True
    )

def generate_world_build():
    prompt = "You are the Dungeon Master of a fantasy world. Describe the world vividly for the player's adventure."
    chat_session = genai.GenerativeModel(
        model_name="gemini-1.5-flash", 
        generation_config=generation_config,
        safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    }
    ).start_chat(history=[])
    response = chat_session.send_message(prompt)
    return response.text.strip()

def roll_dice_stat():
    rolls = sorted([random.randint(1, 6) for _ in range(4)])
    total = sum(rolls[1:])
    return total, rolls

def select_dice():
    dice_type = random.choice(list(DICE.keys()))
    return dice_type

def evaluate_outcome(dice_result, stat_value, ai_scenario):
    difficulty_keywords = {
        "easy": 5, "simple": 6, "moderate": 10,
        "challenging": 15, "hard": 18, "impossible": 20
    }
    threshold = 10
    for keyword, value in difficulty_keywords.items():
        if keyword in ai_scenario.lower():
            threshold = value
            break
    outcome = dice_result + (stat_value // 2)
    return "Success!" if outcome >= threshold else "Failure!"

def determine_stat_from_input(player_input):
    """Dynamically determine the appropriate stat to check based on the player's input."""
    stat = None
    
    actions_strength = re.search(r'\b(punch|hit|attack|strike|throw)\b', player_input, re.IGNORECASE)
    actions_dexterity = re.search(r'\b(run|dodge|jump|sneak)\b', player_input, re.IGNORECASE)
    actions_constitution = re.search(r'\b(endure|withstand|resist|survive)\b', player_input, re.IGNORECASE)
    actions_intelligence = re.search(r'\b(think|analyze|solve|study)\b', player_input, re.IGNORECASE)
    actions_wisdom = re.search(r'\b(perceive|sense|notice|discern)\b', player_input, re.IGNORECASE)
    actions_charisma = re.search(r'\b(talk|persuade|convince|charm)\b', player_input, re.IGNORECASE)

    if actions_strength:
        stat = "Strength"
    elif actions_dexterity:
        stat = "Dexterity"
    elif actions_constitution:
        stat = "Constitution"
    elif actions_intelligence:
        stat = "Intelligence"
    elif actions_wisdom:
        stat = "Wisdom"
    elif actions_charisma:
        stat = "Charisma"

    return stat

@app.route('/')
def index():
    """Home page"""
    session.clear()
    return render_template('index.html')

@app.route('/customize_character', methods=['GET', 'POST'])
def customize_character():
    """Character customization page"""
    if request.method == 'POST':
        session['name'] = request.form['name']
        session['surname'] = request.form['surname']
        session['race'] = request.form['race']
        session['lore'] = request.form['lore']
        session['rolled_stats'] = {stat: None for stat in STATS_ORDER}

        character_description = f"{session['name']} {session['surname']}, a {session['race']}. {session['lore']}"
        image_url = search_character_image(session['name'], session['race'], session['lore'])

        if image_url:
            session['character_image'] = image_url

        return redirect(url_for('roll_stats'))

    return render_template('customize_character.html', races=RACES)

@app.route('/roll_stat_ajax', methods=['POST'])
def roll_stat_ajax():
    stat = request.json.get('stat')
    if 'rolled_stats' not in session:
        session['rolled_stats'] = {stat: None for stat in STATS_ORDER}

    if stat and session['rolled_stats'][stat] is None:
        stat_value, dice_rolls = roll_dice_stat()
        session['rolled_stats'][stat] = stat_value
        session.modified = True
        return jsonify({'stat': stat, 'value': stat_value})

    return jsonify({'error': 'Invalid request or stat already rolled'}), 400

@app.route('/check_all_stats_rolled', methods=['GET'])
def check_all_stats_rolled():
    """Check if all stats have been rolled"""
    all_stats_rolled = all(session['rolled_stats'].values())
    return jsonify({'all_stats_rolled': all_stats_rolled})

@app.route('/roll_stats', methods=['GET', 'POST'])
def roll_stats():
    """Page for rolling stats all at once"""
    stats_order = STATS_ORDER

    if 'rolled_stats' not in session:
        session['rolled_stats'] = {stat: None for stat in STATS_ORDER}

    if request.method == 'POST':
        if 'next_section' in request.form:
            return redirect(url_for('world_build'))

    all_stats_rolled = all(session['rolled_stats'].values())

    return render_template(
        'roll_stats.html',
        stats_order=stats_order,
        rolled_stats=session['rolled_stats'],
        all_stats_rolled=all_stats_rolled
    )

@app.route('/roll_dice_ajax', methods=['POST'])
def roll_dice_ajax():
    """Handle the AJAX request to roll the dice."""
    data = request.get_json()
    stat_to_roll = data.get('stat')

    if stat_to_roll and 'rolled_stats' in session:
        dice_choice = select_dice()
        dice_result = random.randint(1, DICE[dice_choice][0])

        stat_value = session['rolled_stats'][stat_to_roll]
        threshold = 10
        outcome = evaluate_outcome(dice_result, stat_value, session.get('last_scenario'))

        return jsonify({
            'dice_result': dice_result,
            'outcome': outcome,
        })

    return jsonify({'error': 'Invalid stat or session data missing'}), 400

@app.route('/process_dice_outcome', methods=['POST'])
def process_dice_outcome():
    """Process the outcome of the dice roll and move the game forward."""
    outcome = request.form.get('outcome')

    if not outcome:
        return redirect(url_for('play'))

    if "Failure!" in outcome:
        session['health'] -= 1
        if session['health'] <= 0:
            return redirect(url_for('death'))

    world_build = session['world']
    player_lore = session.get('lore', '')

    prompt = f"""
    World setting: {world_build}
    Player's lore: {player_lore}
    Last outcome: {outcome}

    Describe the result of the {outcome.lower()} briefly, without excessive detail.
    Avoid giving choices, long descriptions, or additional tasks.
    """

    chat_session = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        }
    ).start_chat(history=[])

    next_scenario = chat_session.send_message(prompt).text.strip()

    if next_scenario == session.get('last_scenario'):
        next_scenario = f"New events happen following the last outcome: {outcome}"

    session['last_scenario'] = next_scenario
    session['game_log'].append(f"Scenario: {next_scenario}")

    session['game_log'] = session['game_log'][-MAX_LOG_SIZE:]
    session['last_outcome'] = None
    session['roll_needed'] = False
    session['stat_to_roll'] = None
    session.modified = True

    return redirect(url_for('play'))

@app.route('/world_build', methods=['GET', 'POST'])
def world_build():
    """World-building page, where the player creates their world"""
    if 'world' not in session:
        session['world'] = generate_world_build()

    if 'game_log' not in session:
        session['game_log'] = [f"World: {session['world']}"]

    if request.method == 'POST':
        return redirect(url_for('play'))

    return render_template('world_build.html', world=session['world'])


MAX_LOG_SIZE = 5

def trim_ai_response(response):
    """Trim AI response to a defined max length."""
    if len(response) > MAX_TEXT_LENGTH:
        return response[:MAX_TEXT_LENGTH].strip() + "..."
    return response

@app.route('/play', methods=['GET', 'POST'])
def play():
    if 'game_log' not in session:
        session['game_log'] = []
    if 'roll_needed' not in session:
        session['roll_needed'] = False
    if 'stat_to_roll' not in session:
        session['stat_to_roll'] = None
    if 'last_outcome' not in session:
        session['last_outcome'] = None
    if 'last_scenario' not in session:
        session['last_scenario'] = None
    if 'health' not in session:
        session['health'] = 5
    # if 'tts_audio_path' not in session:
    #     session['tts_audio_path'] = None
    if 'scenario_for_audio' not in session:
        session['scenario_for_audio'] = None

    session['game_log'] = session['game_log'][-MAX_LOG_SIZE:]

    if not session.get('last_scenario'):
        if 'world' in session and 'lore' in session:
            session['last_scenario'] = generate_first_scenario(session['world'], session['lore'])
            session['game_log'].append(f"Scenario: {session['last_scenario']}")

            # Generate TTS for the first scenario
            # tts_audio_path = generate_tts_for_scenario(session['last_scenario'])
            # session['tts_audio_path'] = tts_audio_path
            session['scenario_for_audio'] = session['last_scenario']
        else:
            session['last_scenario'] = "No scenario available."

    roll_needed = session.get('roll_needed', False)
    stat_to_roll = session.get('stat_to_roll', None)

    if request.method == 'POST':
        player_input = request.form['player_input']
        world_build = session['world']
        player_lore = session.get('lore', '')

        stat = determine_stat_from_input(player_input)
        if stat:
            session['roll_needed'] = True
            session['stat_to_roll'] = stat
            session.modified = True
            return redirect(url_for('play'))

        prompt = f"""
        World setting: {world_build}
        Player's lore: {player_lore}
        Player's input: {player_input}

        Continue the story. Create a new scenario based on the player's actions.
        """

        chat_session = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config=generation_config,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            }
        ).start_chat(history=[])

        ai_scenario = chat_session.send_message(prompt).text.strip()

        if ai_scenario == session.get('last_scenario'):
            ai_scenario = f"A new event unfolds based on your input: {player_input}"

        if ai_scenario != session.get('scenario_for_audio'):
            # Delete the previous audio file if it exists
            # if session['tts_audio_path']:
            #     try:
            #         os.remove(session['tts_audio_path'])
            #     except OSError:
            #         pass

            # session['tts_audio_path'] = None

            # Generate TTS for the new scenario
            # tts_audio_path = generate_tts_for_scenario(ai_scenario)
            # session['tts_audio_path'] = tts_audio_path
            session['scenario_for_audio'] = ai_scenario

        session['last_scenario'] = ai_scenario
        session['game_log'].append(f"Scenario: {ai_scenario}")
        session['game_log'] = session['game_log'][-MAX_LOG_SIZE:]
        session['roll_needed'] = False
        session['stat_to_roll'] = None
        session.modified = True

        return redirect(url_for('play'))

    return render_template(
        'play.html',
        game_log=session['game_log'],
        stats=session.get('rolled_stats'),
        last_scenario=session.get('last_scenario'),
        roll_needed=session.get('roll_needed'),
        stat_to_roll=session.get('stat_to_roll'),
        last_outcome=session.get('last_outcome'),
        health=session.get('health', 5),
        character_image=session.get('character_image'),
        # tts_audio_path=session.get('tts_audio_path')
    )

@app.route('/death')
def death():
    """Handle player's death and redirect to homepage."""
    session.clear()
    return render_template('death.html', message="YOU DIED! Start again?")

@app.route('/roll_dice', methods=['POST'])
def roll_dice():
    """Handle dice roll and process outcome."""
    stat_to_roll = session.get('stat_to_roll')

    if stat_to_roll:
        dice_choice = select_dice()
        dice_result = random.randint(1, DICE[dice_choice][0])
        
        stat_value = session['rolled_stats'][stat_to_roll]
        scenario = session['last_scenario']
        outcome = evaluate_outcome(dice_result, stat_value, scenario)

        if "danger" in scenario.lower() and "Failure!" in outcome:
            session['health'] -= 1
            if session['health'] <= 0:
                return redirect(url_for('death'))

        session['last_outcome'] = f"Rolled {dice_choice}: {dice_result} ({outcome})"
        session.modified = True

    return redirect(url_for('play'))

def generate_first_scenario(world_build, player_lore):
    """Generate the first story scenario using the world and player's lore."""
    prompt = f"""
    World setting: {world_build}
    Player's lore: {player_lore}

    Begin the player's adventure in a concise and focused manner. Avoid describing the surroundings in excessive detail. 
    Do not give predefined choices, quests, or tasks. Only continue the story based on the player's actions. 
    Keep the responses short and relevant to the immediate situation.
    """
    chat_session = genai.GenerativeModel(
        model_name="gemini-1.5-flash", 
        generation_config=generation_config,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        }
    ).start_chat(history=[])
    response = chat_session.send_message(prompt)
    return response.text.strip()

if __name__ == '__main__':
    app.run(debug=True)
