# AI-Powered Code Review Backend

A comprehensive FastAPI backend for an AI-powered code review system. This backend provides intelligent code analysis using Google Gemini and OpenAI APIs, with full user authentication, real-time updates, and comprehensive analytics.

## 🚀 Features

### Core Functionality
- **AI-Powered Code Review**: Integration with Google Gemini and OpenAI APIs
- **Asynchronous Processing**: Non-blocking review processing with background tasks
- **Intelligent Caching**: Code hash-based caching for identical submissions
- **Real-time Updates**: WebSocket integration for live status updates
- **Rate Limiting**: Configurable rate limiting (10 reviews per IP per hour)

### User Management
- **JWT Authentication**: Secure token-based authentication
- **User Registration**: Email/password registration with password hashing
- **Google OAuth**: Social login integration with Google ID token verification
- **User Profiles**: Personal review history and statistics
- **Password Security**: Bcrypt password hashing with salt

### Data Management
- **MongoDB Integration**: Async MongoDB operations with Motor driver
- **Pagination**: Efficient data loading with skip/limit pagination
- **Filtering**: Advanced filtering by language, status, date range
- **Export Functionality**: CSV export with filtering capabilities
- **Data Validation**: Pydantic models for request/response validation

### Analytics & Monitoring
- **Comprehensive Statistics**: Overall metrics and performance analytics
- **Issue Analysis**: Common issues identification and categorization
- **Language Breakdown**: Per-language statistics and insights
- **Performance Metrics**: Review processing times and success rates
- **Error Tracking**: Structured error handling and logging

### Security & Performance
- **CORS Configuration**: Configurable cross-origin resource sharing
- **Input Validation**: Comprehensive input sanitization and validation
- **Error Handling**: Graceful error handling with proper HTTP status codes
- **Database Indexing**: Optimized database queries with proper indexing
- **Retry Logic**: Exponential backoff for AI API calls

## 🛠️ Tech Stack

- **Framework**: FastAPI with Uvicorn ASGI server
- **Database**: MongoDB with Motor (async driver)
- **Authentication**: JWT with python-jose and passlib
- **AI Integration**: Google Gemini API and OpenAI API
- **Validation**: Pydantic for data validation and serialization
- **Security**: Bcrypt for password hashing, CORS middleware
- **Real-time**: WebSocket support for live updates
- **Deployment**: Docker and Docker Compose

## 📋 Prerequisites

- Python 3.10+
- MongoDB 4.4+
- Docker and Docker Compose (optional)
- Google Gemini API key or OpenAI API key

## 🚀 Quick Start

### 1. Environment Setup

Create a `.env` file in the project root:

```env
# AI API Keys (at least one required)
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Database Configuration
MONGODB_URI=mongodb://mongodb:27017

# Security
JWT_SECRET=your_jwt_secret_key_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS Configuration
CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173

# Application URLs
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# Rate Limiting
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=3600
```

### 2. Docker Deployment (Recommended)

```bash
# Clone and start services
git clone <repository-url>
cd Backend-Ai-Powered-Code-Review
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

### 3. Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 Project Structure

```
app/
├── api/
│   ├── auth/
│   │   └── routes.py          # Authentication endpoints
│   └── reviews/
│       ├── schema.py          # Pydantic models
│       └── viewer.py          # Review endpoints and logic
├── core/
│   └── security.py            # JWT and password utilities
├── database/
│   └── database.py            # MongoDB connection and setup
├── models/
│   └── user.py                # User data models
└── main.py                    # FastAPI application entry point
```

## 🔧 API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/register` | User registration | No |
| POST | `/api/auth/login` | Email/password login | No |
| POST | `/api/auth/google` | Google OAuth login | No |
| GET | `/api/auth/me` | Get current user | Yes |

### Review Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/reviews` | Submit code for review | Optional |
| GET | `/api/reviews/id/{id}` | Get specific review | No |
| GET | `/api/reviews` | List reviews with filters | No |
| GET | `/api/reviews/mine` | Get user's reviews | Yes |
| GET | `/api/reviews/stats` | Get review statistics | No |
| GET | `/api/reviews/export` | Export reviews as CSV | No |
| GET | `/api/stats` | Alias for stats endpoint | No |

### Real-time Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/api/reviews/ws/{review_id}` | WebSocket for live updates |

### Utility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/docs` | Interactive API documentation |
| GET | `/redoc` | Alternative API documentation |

## 🔐 Authentication

### JWT Token Structure

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "exp": 1234567890,
  "iat": 1234567890
}
```

### Authentication Flow

1. **Registration**: User provides email and password
2. **Password Hashing**: Bcrypt with salt for security
3. **JWT Generation**: Token with user information and expiration
4. **Token Storage**: Client stores token in localStorage
5. **Request Authentication**: Bearer token in Authorization header
6. **Token Validation**: Server validates token on protected routes

### Google OAuth Integration

```python
# Google OAuth flow
POST /api/auth/google
{
  "id_token": "google_id_token_here"
}
```

## 📊 Data Models

### User Model

```python
class UserInDB(BaseModel):
    id: str
    email: str
    hashed_password: str
    created_at: datetime
    is_active: bool = True
```

### Review Model

```python
class ReviewResponse(BaseModel):
    id: str
    language: str
    code: str
    status: str
    feedback: Optional[dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    user_id: Optional[str] = None
    ip_address: str
    code_hash: str
```

### Statistics Model

```python
class StatsResponse(BaseModel):
    total_reviews: int
    completed_reviews: int
    failed_reviews: int
    average_score: float
    common_issues: List[dict]
    language_stats: List[dict]
```

## 🔄 Real-time Features

### WebSocket Integration

```python
# WebSocket endpoint for live updates
@app.websocket("/api/reviews/ws/{review_id}")
async def review_status_ws(websocket: WebSocket, review_id: str):
    # Real-time status updates
    # Automatic connection management
    # Error handling and reconnection
```

### Status Updates

- **pending**: Review queued for processing
- **in_progress**: AI analysis in progress
- **completed**: Review completed successfully
- **failed**: Review failed with error

## 🚀 Performance Optimizations

### Database Indexing

```python
# Automatic index creation on startup
indexes = [
    ("created_at", 1),
    ("language", 1),
    ("status", 1),
    ("ip", 1),
    ("created_at", 1),
    ("code_hash", 1),
    ("user_id", 1)
]
```

### Caching Strategy

- **Code Hash Caching**: Identical code submissions return cached results
- **Database Query Optimization**: Proper indexing and aggregation pipelines
- **Response Caching**: Frequently accessed data cached in memory

### Retry Logic

```python
# Exponential backoff for AI API calls
async def process_review_with_retry(code, language, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await call_ai_api(code, language)
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2 ** attempt)
```

## 🧪 Development

### Available Scripts

```bash
# Development server with auto-reload
uvicorn app.main:app --reload

# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Run with specific workers
uvicorn app.main:app --workers 4

# Run with Docker
docker-compose up -d --build
```

### Code Quality

- **Type Hints**: Full type annotation with Python 3.10+ features
- **Pydantic Validation**: Comprehensive data validation
- **Error Handling**: Structured error responses
- **Logging**: Comprehensive logging for debugging
- **Documentation**: Auto-generated OpenAPI/Swagger docs

## 🐛 Troubleshooting

### Common Issues

1. **MongoDB Connection**
   ```bash
   # Check MongoDB status
   docker-compose ps mongodb
   
   # View MongoDB logs
   docker-compose logs mongodb
   ```

2. **AI API Errors**
   ```bash
   # Check API key configuration
   echo $GEMINI_API_KEY
   echo $OPENAI_API_KEY
   ```

3. **CORS Issues**
   ```bash
   # Update CORS_ALLOW_ORIGINS in .env
   CORS_ALLOW_ORIGINS=http://localhost:3000,http://localhost:5173
   ```

4. **Rate Limiting**
   ```bash
   # Adjust rate limits in .env
   RATE_LIMIT_REQUESTS=20
   RATE_LIMIT_WINDOW=3600
   ```

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Monitoring & Analytics

### Built-in Metrics

- **Review Processing Times**: Track AI API response times
- **Success/Failure Rates**: Monitor review completion rates
- **User Activity**: Track user engagement and usage patterns
- **Error Rates**: Monitor and alert on error conditions

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/api/health

# Detailed status
curl http://localhost:8000/api/reviews/stats
```

## 🔒 Security Considerations

### Authentication Security

- **JWT Secret**: Use strong, random JWT secrets
- **Token Expiration**: Configurable token expiration times
- **Password Hashing**: Bcrypt with salt for password security
- **Input Validation**: Comprehensive input sanitization

### API Security

- **Rate Limiting**: Prevent abuse and DoS attacks
- **CORS Configuration**: Restrict cross-origin requests
- **Input Validation**: Pydantic models for data validation
- **Error Handling**: Avoid information leakage in error messages

### Database Security

- **Connection Security**: Secure MongoDB connection strings
- **Data Validation**: Server-side validation of all inputs
- **Index Security**: Proper database indexing for performance

## 🚀 Deployment

### Production Configuration

```env
# Production environment variables
MONGODB_URI=mongodb://mongodb:27017
JWT_SECRET=your_strong_production_secret
CORS_ALLOW_ORIGINS=https://yourdomain.com
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600
```

### Docker Production

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URI=mongodb://mongodb:27017
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - mongodb
  
  mongodb:
    image: mongo:6.0
    volumes:
      - mongodb_data:/data/db
    ports:
      - "27017:27017"

volumes:
  mongodb_data:
```

### Environment-Specific Configs

- **Development**: Local MongoDB, relaxed CORS, debug logging
- **Staging**: Production-like setup with test data
- **Production**: Optimized performance, strict security, monitoring

## 🤝 Contributing

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Set up development environment
4. Make your changes
5. Add tests if applicable
6. Submit a pull request

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Add docstrings for public functions
- Include error handling
- Write comprehensive tests

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

- Create an issue in the repository
- Check the troubleshooting section
- Review the API documentation at `/docs`
- Contact the development team

## 🔄 Version History

- **v1.0.0**: Initial release with basic code review functionality
- **v1.1.0**: Added user authentication and JWT support
- **v1.2.0**: Implemented real-time updates and WebSocket integration
- **v1.3.0**: Added comprehensive analytics and export functionality
- **v1.4.0**: Enhanced security and performance optimizations

---

**Built with ❤️ using FastAPI, MongoDB, and AI APIs**