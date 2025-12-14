# Admin Access Guide

## Quick Start - Create Admin User

### Option 1: Using the Helper Script (Recommended)

```bash
# Create default admin (username: admin, password: admin)
./scripts/make_admin.sh

# Make existing user an admin
./scripts/make_admin.sh your_username

# Create new admin with custom password
./scripts/make_admin.sh myuser mypassword

# Create new admin with custom email
./scripts/make_admin.sh myuser mypassword myuser@example.com
```

### Option 2: Using Django's createsuperuser Command

```bash
# If using Docker
docker compose exec web python manage.py createsuperuser

# If running locally
cd WebUI
python manage.py createsuperuser
```

### Option 3: Using the Python Script Directly

```bash
# If using Docker
docker compose exec web python make_admin.py

# If running locally
cd WebUI
python make_admin.py [username] [password] [email]
```

---

## Admin Interface URLs

- **Django Admin**: http://localhost:8000/admin/
- **Main App**: http://localhost:8000/
- **Celery Monitor (Flower)**: http://localhost:5555/

---

## Default Credentials

If you use the quick script without arguments:
```
Username: admin
Password: admin
```

**⚠️ IMPORTANT**: Change this password immediately after first login!

---

## Troubleshooting

### "Docker services not running"

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps
```

### "User already exists"

If you get an error that the user already exists, you can either:

1. **Make the existing user an admin:**
   ```bash
   ./scripts/make_admin.sh existing_username
   ```

2. **Reset the user's password:**
   ```bash
   docker compose exec web python manage.py changepassword username
   ```

3. **Delete and recreate (caution: loses user data):**
   ```bash
   docker compose exec web python manage.py shell
   >>> from django.contrib.auth.models import User
   >>> User.objects.get(username='admin').delete()
   >>> exit()
   ./scripts/make_admin.sh
   ```

### "Permission denied"

```bash
# Make scripts executable
chmod +x scripts/make_admin.sh
chmod +x WebUI/make_admin.py
```

### Cannot login to admin

1. **Check user exists and is admin:**
   ```bash
   docker compose exec web python make_admin.py
   ```
   This will list all users and their admin status.

2. **Verify password:**
   ```bash
   docker compose exec web python manage.py changepassword admin
   ```

3. **Check Django admin is accessible:**
   - Ensure web service is running: `docker compose ps web`
   - Check logs: `docker compose logs web`
   - Visit: http://localhost:8000/admin/

---

## Common Tasks

### List All Users

```bash
docker compose exec web python manage.py shell
>>> from django.contrib.auth.models import User
>>> for u in User.objects.all():
...     print(f"{u.username} - Admin: {u.is_superuser}")
>>> exit()
```

Or use the script:
```bash
docker compose exec web python make_admin.py
```

### Change Password

```bash
docker compose exec web python manage.py changepassword username
```

### Remove Admin Privileges

```bash
docker compose exec web python manage.py shell
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='username')
>>> user.is_superuser = False
>>> user.is_staff = False
>>> user.save()
>>> exit()
```

### Delete User

```bash
docker compose exec web python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.get(username='username').delete()
>>> exit()
```

---

## Security Best Practices

1. **Change default password immediately**
   ```bash
   docker compose exec web python manage.py changepassword admin
   ```

2. **Use strong passwords** (12+ characters, mixed case, numbers, symbols)

3. **Limit admin users** (only create admin accounts when necessary)

4. **Regular password rotation** (change passwords every 90 days)

5. **Use environment variables for sensitive data**
   ```bash
   # In production, set in .env file
   SECRET_KEY=your-secret-key-here
   DEBUG=False
   ALLOWED_HOSTS=yourdomain.com
   ```

---

## Production Deployment

For production, **do not use the quick script**. Instead:

1. **Create admin via Django command:**
   ```bash
   python manage.py createsuperuser
   ```

2. **Use strong credentials**

3. **Restrict admin access:**
   - Use HTTPS only
   - Restrict admin URL to specific IPs
   - Use 2FA (django-two-factor-auth)
   - Enable Django security middleware

4. **Monitor admin logins:**
   - Check Django admin logs
   - Use django-axes for failed login tracking
   - Set up alerting for admin access

---

## Files Reference

- `WebUI/make_admin.py` - Python script for user management
- `scripts/make_admin.sh` - Bash wrapper for Docker
- `WebUI/config/settings.py` - Django settings (LOGIN_URL, etc.)
- `WebUI/app/admin.py` - Django admin configuration

---

**Quick Links:**
- [Django Admin Documentation](https://docs.djangoproject.com/en/stable/ref/contrib/admin/)
- [User Authentication](https://docs.djangoproject.com/en/stable/topics/auth/)
- [Main README](README.md)
