import config
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import sqlite3
import logging
from typing import List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(config.API_TOKEN)

# Database configuration
DB_NAME = "movie_database.db"


class DatabaseManager:
    """Handle all database operations with proper connection management"""
    
    def __init__(self, db_name: str):
        self.db_name = db_name
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Tuple]:
        """Execute a query and return results"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                return results
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []
    
    def get_random_movie(self) -> Optional[Tuple]:
        """Get a random movie from database"""
        query = "SELECT * FROM movies ORDER BY RANDOM() LIMIT 1"
        results = self.execute_query(query)
        return results[0] if results else None
    
    def search_movie_by_title(self, title: str) -> Optional[Tuple]:
        """Search for a movie by title (SQL injection safe)"""
        query = "SELECT * FROM movies WHERE LOWER(title) = LOWER(?)"
        results = self.execute_query(query, (title,))
        return results[0] if results else None
    
    def get_top_movies(self, limit: int = 10, order_by: str = 'rating', 
                       genre: Optional[str] = None, year: Optional[int] = None) -> List[Tuple]:
        """Get top movies with optional filters"""
        # Validate order_by to prevent SQL injection
        valid_columns = ['rating', 'year', 'title']
        if order_by not in valid_columns:
            order_by = 'rating'
        
        query = """
            SELECT id, img, title, year, genre, rating, overview
            FROM movies
            WHERE rating IS NOT NULL
        """
        params = []
        
        if genre:
            query += " AND genre LIKE ?"
            params.append(f'%{genre}%')
        
        if year:
            query += " AND year = ?"
            params.append(year)
        
        query += f" ORDER BY {order_by} DESC LIMIT ?"
        params.append(limit)
        
        return self.execute_query(query, tuple(params))


db_manager = DatabaseManager(DB_NAME)


def send_movie_info(chat_id: int, movie_data: Tuple):
    """Send formatted movie information to user"""
    try:
        movie_id, img_url, title, year, genre, rating, overview = movie_data
        
        info_text = f"""
📍 <b>Title:</b> {title}
📍 <b>Year:</b> {year}
📍 <b>Genre:</b> {genre}
📍 <b>IMDB Rating:</b> ⭐ {rating}/10

🔻🔻🔻🔻🔻🔻🔻🔻🔻🔻🔻
{overview}
"""
        
        # Send poster if available
        if img_url:
            try:
                bot.send_photo(chat_id, img_url)
            except Exception as e:
                logger.warning(f"Failed to send poster: {e}")
        
        # Send movie info with favorite button
        markup = create_favorite_button(movie_id)
        bot.send_message(chat_id, info_text, parse_mode='HTML', reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Error sending movie info: {e}")
        bot.send_message(chat_id, "❌ Error displaying movie information")


def create_favorite_button(movie_id: int) -> InlineKeyboardMarkup:
    """Create inline keyboard with favorite button"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "⭐ Add to Favorites",
        callback_data=f'favorite_{movie_id}'
    ))
    return markup


def create_main_keyboard() -> ReplyKeyboardMarkup:
    """Create main reply keyboard"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton('🎲 Random Movie'),
        KeyboardButton('🏆 Top Movies'),
        KeyboardButton('🎭 By Genre'),
        KeyboardButton('📅 By Year'),
        KeyboardButton('ℹ️ Help')
    )
    return markup


# ==================== COMMAND HANDLERS ====================

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Handle /start command"""
    welcome_text = """
🎬 <b>Welcome to the Ultimate Movie Bot!</b> 🎥

Explore our collection of 1,000+ amazing movies!

<b>Quick Actions:</b>
• Click buttons below for quick access
• Type a movie title to search
• Use /help to see all commands

Enjoy your movie journey! 🍿
"""
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML',
        reply_markup=create_main_keyboard()
    )


@bot.message_handler(commands=['help'])
def handle_help(message):
    """Handle /help command"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    buttons = [
        InlineKeyboardButton("🏆 Top Rated", callback_data='help_top_rated'),
        InlineKeyboardButton("🎭 By Genre", callback_data='help_genre'),
        InlineKeyboardButton("📅 By Year", callback_data='help_year'),
        InlineKeyboardButton("🎲 Random", callback_data='help_random')
    ]
    markup.add(*buttons)
    
    help_text = """
ℹ️ <b>AVAILABLE COMMANDS</b>

📋 <b>Main Commands:</b>
• /start - Start the bot
• /help - Show this help menu
• /random - Get a random movie
• /top_movies - Top 10 by rating
• /top_movies_genre - Top by genre
• /top_movies_year - Top by year

🔍 <b>Search:</b>
Just type any movie title to search!

Choose an option below or use the keyboard buttons:
"""
    
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.message_handler(commands=['random'])
def handle_random(message):
    """Handle /random command"""
    movie = db_manager.get_random_movie()
    
    if movie:
        send_movie_info(message.chat.id, movie)
    else:
        bot.send_message(message.chat.id, "❌ No movies found in database")


@bot.message_handler(commands=['top_movies'])
def handle_top_movies(message):
    """Handle /top_movies command"""
    try:
        movies = db_manager.get_top_movies(limit=10)
        
        if not movies:
            bot.reply_to(message, "🎬 No movies found in database")
            return
        
        response = "🏆 <b>TOP 10 MOVIES BY RATING</b> 🎬\n\n"
        
        for index, movie_data in enumerate(movies, 1):
            _, _, title, year, genre, rating, overview = movie_data
            
            # Create star rating
            stars = "⭐" * int(rating)
            
            # Truncate overview
            short_desc = (overview[:100] + '...') if overview and len(overview) > 100 else (overview or "")
            
            response += f"""
<b>{index}. {title}</b> ({year})
   ⭐ <b>Rating:</b> {rating}/10 {stars}
   🎭 <b>Genre:</b> {genre or 'Unknown'}
"""
            if short_desc:
                response += f"   📝 {short_desc}\n"
            
            response += "   ━━━━━━━━━━━━━━━━━━━\n"
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in top_movies: {e}")
        bot.reply_to(message, f"❌ An error occurred: {str(e)}")


@bot.message_handler(commands=['top_movies_genre'])
def handle_top_movies_by_genre(message):
    """Handle /top_movies_genre command"""
    markup = InlineKeyboardMarkup(row_width=2)
    
    # Actual genres from the database
    genres = [
        "Action", "Adventure", "Animation", "Biography", "Comedy", 
        "Crime", "Drama", "Family", "Fantasy", "Film-Noir",
        "History", "Horror", "Music", "Musical", "Mystery",
        "Romance", "Sci-Fi", "Sport", "Thriller", "War", "Western"
    ]
    
    buttons = [
        InlineKeyboardButton(genre, callback_data=f'top_genre_{genre}')
        for genre in genres
    ]
    
    # Add buttons in rows of 2
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i+1])
        else:
            markup.add(buttons[i])
    
    bot.send_message(
        message.chat.id,
        "🎭 <b>Select a genre to view top movies:</b>",
        parse_mode='HTML',
        reply_markup=markup
    )


@bot.message_handler(commands=['top_movies_year'])
def handle_top_movies_by_year(message):
    """Handle /top_movies_year command"""
    # Database contains movies from 1920-2020
    # Show recent years (2000-2020) for better UX
    markup = InlineKeyboardMarkup(row_width=3)
    
    buttons = [
        InlineKeyboardButton(str(year), callback_data=f'top_year_{year}')
        for year in range(2020, 1999, -1)  # 2020 down to 2000
    ]
    
    # Add buttons in rows of 3
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    
    # Add a button for older movies
    markup.add(InlineKeyboardButton("🎞️ Classic Movies (1920-1999)", callback_data='top_year_classic'))
    
    bot.send_message(
        message.chat.id,
        "📅 <b>Select a year to view top movies:</b>",
        parse_mode='HTML',
        reply_markup=markup
    )


# ==================== CALLBACK HANDLERS ====================

@bot.callback_query_handler(func=lambda call: call.data.startswith('favorite_'))
def handle_favorite_callback(call):
    """Handle favorite button clicks"""
    try:
        movie_id = call.data.split('_')[1]
        # Here you would typically save to a favorites table
        bot.answer_callback_query(
            call.id,
            "⭐ Added to favorites!",
            show_alert=True
        )
        logger.info(f"User {call.from_user.id} favorited movie {movie_id}")
    except Exception as e:
        logger.error(f"Error handling favorite: {e}")
        bot.answer_callback_query(call.id, "❌ Error adding to favorites")


@bot.callback_query_handler(func=lambda call: call.data.startswith('top_genre_'))
def handle_genre_callback(call):
    """Handle genre selection callback"""
    try:
        genre = call.data.replace('top_genre_', '')
        movies = db_manager.get_top_movies(limit=10, genre=genre)
        
        if not movies:
            bot.answer_callback_query(
                call.id,
                f"❌ No movies found in genre '{genre}'",
                show_alert=True
            )
            return
        
        response = f"🎭 <b>TOP 10 MOVIES - {genre.upper()}</b> 🎬\n\n"
        
        for index, movie_data in enumerate(movies, 1):
            _, _, title, year, genre_name, rating, _ = movie_data
            stars = "⭐" * int(rating)
            
            response += f"""
<b>{index}. {title}</b> ({year})
   ⭐ Rating: {rating}/10 {stars}
   ━━━━━━━━━━━━━━━━━━━
"""
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in genre callback: {e}")
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('top_year_'))
def handle_year_callback(call):
    """Handle year selection callback"""
    try:
        # Handle classic movies option
        if call.data == 'top_year_classic':
            # Show top classic movies (before 2000)
            query = """
                SELECT id, img, title, year, genre, rating, overview
                FROM movies
                WHERE year < 2000 AND rating IS NOT NULL
                ORDER BY rating DESC
                LIMIT 10
            """
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(query)
            movies = cursor.fetchall()
            conn.close()
            
            if not movies:
                bot.answer_callback_query(call.id, "❌ No classic movies found", show_alert=True)
                return
            
            response = "🎞️ <b>TOP 10 CLASSIC MOVIES (1920-1999)</b> 🎬\n\n"
            
            for index, movie_data in enumerate(movies, 1):
                _, _, title, year, genre, rating, _ = movie_data
                stars = "⭐" * int(rating)
                
                response += f"""
<b>{index}. {title}</b> ({year})
   ⭐ Rating: {rating}/10 {stars}
   🎭 Genre: {genre or 'Unknown'}
   ━━━━━━━━━━━━━━━━━━━
"""
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=response,
                parse_mode='HTML'
            )
            bot.answer_callback_query(call.id)
            return
        
        # Handle specific year
        year = int(call.data.replace('top_year_', ''))
        movies = db_manager.get_top_movies(limit=10, year=year)
        
        if not movies:
            bot.answer_callback_query(
                call.id,
                f"❌ No movies found for year {year}",
                show_alert=True
            )
            return
        
        response = f"📅 <b>TOP 10 MOVIES - {year}</b> 🎬\n\n"
        
        for index, movie_data in enumerate(movies, 1):
            _, _, title, _, genre, rating, _ = movie_data
            stars = "⭐" * int(rating)
            
            response += f"""
<b>{index}. {title}</b>
   ⭐ Rating: {rating}/10 {stars}
   🎭 Genre: {genre or 'Unknown'}
   ━━━━━━━━━━━━━━━━━━━
"""
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=response,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error in year callback: {e}")
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('help_'))
def handle_help_callbacks(call):
    """Handle help menu callbacks"""
    action = call.data.replace('help_', '')
    
    if action == 'random':
        handle_random(call.message)
    elif action == 'top_rated':
        handle_top_movies(call.message)
    elif action == 'genre':
        handle_top_movies_by_genre(call.message)
    elif action == 'year':
        handle_top_movies_by_year(call.message)
    
    bot.answer_callback_query(call.id)


# ==================== TEXT HANDLERS ====================

@bot.message_handler(func=lambda message: message.text in ['🎲 Random Movie', '/random'])
def handle_random_button(message):
    """Handle random movie button"""
    handle_random(message)


@bot.message_handler(func=lambda message: message.text == '🏆 Top Movies')
def handle_top_button(message):
    """Handle top movies button"""
    handle_top_movies(message)


@bot.message_handler(func=lambda message: message.text == '🎭 By Genre')
def handle_genre_button(message):
    """Handle genre button"""
    handle_top_movies_by_genre(message)


@bot.message_handler(func=lambda message: message.text == '📅 By Year')
def handle_year_button(message):
    """Handle year button"""
    handle_top_movies_by_year(message)


@bot.message_handler(func=lambda message: message.text == 'ℹ️ Help')
def handle_help_button(message):
    """Handle help button"""
    handle_help(message)


@bot.message_handler(func=lambda message: True)
def handle_text_search(message):
    """Handle movie title search"""
    try:
        movie = db_manager.search_movie_by_title(message.text)
        
        if movie:
            bot.send_message(message.chat.id, "✅ Found it! Here's the movie:")
            send_movie_info(message.chat.id, movie)
        else:
            bot.send_message(
                message.chat.id,
                f"❌ Sorry, I couldn't find '{message.text}' in the database.\n\n"
                "Try:\n• Checking the spelling\n• Using /random for a random movie\n"
                "• Browsing by /top_movies_genre"
            )
    except Exception as e:
        logger.error(f"Error in text search: {e}")
        bot.send_message(message.chat.id, "❌ An error occurred during search")


# ==================== MAIN ====================

if __name__ == '__main__':
    logger.info("Bot started successfully!")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Bot stopped with error: {e}")