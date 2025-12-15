# PriceTracker WebUI

A clean, stylish Django web application for tracking product prices with dark/light mode support.

## Features

✨ **Clean, Modern Design**
- Minimalist interface with smooth transitions
- Dark and Light mode with persistent preference
- Responsive layout for all devices
- No fancy graphics, just stylish and functional

🚀 **Public Landing Page**
- No login required to visit the site
- Anyone can search/paste URLs (no login needed)
- Guest users see preview mode with prompt to register
- Feature showcase for visitors
- Clean, non-salesy design

🔐 **User Features** (After Login)
- Track unlimited products
- Real-time price alerts
- Historical price charts
- Multi-store support

## Quick Start

### 1. Activate Virtual Environment

```bash
cd WebUI
source venv/bin/activate
```

### 2. Run the Development Server

```bash
python manage.py runserver
```

### 3. Visit the Application

- **Homepage**: http://127.0.0.1:8000/ (Public - no login required)
- **Admin**: http://127.0.0.1:8000/admin/

### 4. Create Admin User (First Time)

```bash
python manage.py createsuperuser
```

## Project Structure

```
WebUI/
├── venv/                      # Virtual environment
├── config/                    # Django configuration
│   ├── settings.py           # Main settings
│   ├── urls.py               # URL routing
│   ├── celery.py             # Celery configuration
│   └── wsgi.py               # WSGI application
├── app/                       # Main application
│   ├── models.py             # Database models
│   ├── views.py              # View functions
│   ├── admin.py              # Admin customization
│   └── urls.py               # App URLs
├── templates/                 # HTML templates
│   ├── base.html             # Base template with dark/light mode
│   ├── dashboard.html        # Public landing page
│   └── auth/                 # Authentication pages
├── requirements.txt           # Python dependencies
└── manage.py                 # Django management script
```

## Dark/Light Mode

The theme switcher is located in the top navigation bar (moon/sun icon).

- Click to toggle between dark and light themes
- Preference is saved to browser localStorage
- Works for both guests and authenticated users
- All components styled for both themes

## Database Models

Multi-store data model with user subscriptions:

1. **Product** - Normalized product entity (no URL, shared across stores)
2. **Store** - Merchant/retailer entity with domain and rate limits
3. **ProductListing** - Product at a specific store (URL, price, availability)
4. **UserSubscription** - User subscription to a product with priority settings
5. **PriceHistory** - Historical price records per listing
6. **Pattern** - Extraction patterns per store domain
7. **PatternHistory** - Version history for patterns with rollback support
8. **Notification** - User notifications linked to subscriptions
9. **FetchLog** - Fetch attempt logs per listing
10. **UserView** - User engagement analytics
11. **AdminFlag** - Admin attention flags

## Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Create Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Check Configuration

```bash
python manage.py check
```

## Tech Stack

- **Framework**: Django 4.2+
- **Frontend**: HTMX + Tailwind CSS
- **Database**: SQLite (MVP), PostgreSQL (production)
- **Task Queue**: Celery + Redis
- **Charts**: Chart.js
- **Icons**: Heroicons

## License

This project is part of the PriceTracker system.
