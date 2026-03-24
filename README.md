# Django M-Pesa Callback Backend

This Django project handles M-Pesa payment callbacks from Safaricom Daraja API.

## Setup Instructions

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install django djangorestframework django-cors-headers python-dotenv
```

3. Set up environment variables in `.env`:
```
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com
```

4. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Start the server:
```bash
python manage.py runserver
```

## API Endpoints

### POST /api/mpesa/callback/
Receives M-Pesa payment callbacks from Daraja API.

### GET /api/payments/
Retrieve all payment records.

### GET /api/payments/{id}/
Retrieve specific payment record.

## Security Notes

- Configure CORS settings for production
- Use HTTPS in production
- Validate callback requests
- Implement proper authentication
