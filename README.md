# OrbitBank API

OrbitBank API is a robust and scalable banking application backend built with FastAPI, designed to manage users, accounts, transfers, and related financial operations. The application emphasizes security, data integrity, and user experience through asynchronous notifications via email and SMS. It uses JWT authentication, Pydantic for data validation, and AWS services (SES for email, SNS for SMS) for notifications. The API is containerized with Docker and deployed using a CI/CD pipeline with GitHub Actions and AWS ECR/EC2.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Configure Environment Variables](#2-configure-environment-variables)
  - [3. Install Docker and Docker Compose](#3-install-docker-and-docker-compose)
  - [4. Build and Run the Application](#4-build-and-run-the-application)
  - [5. Access the API](#5-access-the-api)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

## Features

-   **User Management:** Register users, verify emails, manage profiles, change passwords, and handle beneficiaries.
-   **Account Management:** Create and manage bank accounts, perform deposits/withdrawals, view balances, and generate statements.
-   **Transfer Management:** Execute secure fund transfers between accounts with transaction logging and notifications.
-   **Notification System:** Asynchronous email (AWS SES) and SMS (AWS SNS) notifications for transactions and account activities.
-   **Security:** JWT-based authentication, password hashing, and robust error handling.
-   **Database Transactions:** Atomic operations with rollbacks to ensure data consistency.
-   **Scalability:** Modular service-based architecture with FastAPI and background tasks for non-blocking operations.
-   **CI/CD Pipeline:** Automated build and deployment to AWS ECR/EC2 using GitHub Actions.

## Architecture

The application is divided into several services, each handling specific banking operations:

-   **User Management (`users.py`):** Manages user registration, verification, profiles, and beneficiaries.
-   **Account Management (`accounts.py`):** Handles account creation, deposits, withdrawals, balances, and statements.
-   **Transfer Management (`transfers.py`):** Processes fund transfers with validation and notifications.
-   **Supporting Services:**
    -   **Transactions (`transactions.py`):** Logs and retrieves transaction details.
    -   **Banks (`banks.py`):** Manages bank institution records.
    -   **Branches (`branches.py`):** Manages bank branch records.
    -   **Account Types (`account_types.py`):** Manages account type definitions.
-   **Notification Services:**
    -   Email notifications via AWS SES.
    -   SMS notifications via AWS SNS.

The application uses PostgreSQL (via `libpq-dev`) for data storage, Docker for containerization, and Uvicorn as the ASGI server. Background tasks ensure non-blocking notification delivery, and Pydantic enforces strict data validation.

## Prerequisites

To run the OrbitBank API locally, ensure you have the following installed:

-   Docker and Docker Compose (for containerized deployment)
-   Python 3.11 (optional, for local development without Docker)
-   Git (for cloning the repository)
-   AWS Account (for SES/SNS configuration, if notifications are enabled)
-   A PostgreSQL database (local or cloud-based)
-   An AWS IAM user with access to SES and SNS (if using notifications)

## Setup Instructions

Follow these steps to set up and run the OrbitBank API on your local machine.

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/orbitbank-api.git
cd orbitbank-api
```

**Note:** Replace `your-username` with the actual repository owner’s username.

### 2. Configure Environment Variables

Create a `.env` file in the `app/` directory based on the following template:

```env
# Database configuration
DATABASE_URL=postgresql://user:password@localhost:5432/orbitbank

# JWT configuration
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# AWS SES configuration (for email notifications)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
SES_SENDER_EMAIL=verified-email@example.com

# AWS SNS configuration (for SMS notifications)
SNS_REGION=us-east-1

# Application settings
APP_ENV=development
```

-   **`DATABASE_URL`**: Replace with your PostgreSQL connection string.
-   **`JWT_SECRET_KEY`**: Generate a secure key (e.g., using `openssl rand -hex 32`).
-   **`AWS_ACCESS_KEY_ID`** and **`AWS_SECRET_ACCESS_KEY`**: Obtain from your AWS IAM user.
-   **`SES_SENDER_EMAIL`**: Use a verified email address in AWS SES.

Ensure the `.env` file is not committed to version control (add it to `.gitignore`).

### 3. Install Docker and Docker Compose

-   **Install Docker:** Follow the [official Docker installation guide](https://docs.docker.com/get-docker/).
-   **Install Docker Compose:** Follow the [official Docker Compose installation guide](https://docs.docker.com/compose/install/).
-   **Verify installation:**
    ```bash
    docker --version
    docker-compose --version
    ```

### 4. Build and Run the Application

Build the Docker image and start the services:

```bash
docker-compose up --build -d
```

This command builds the `bank-api` image and starts the container, exposing port 8000.

Verify the container is running:

```bash
docker ps
```

You should see a container named `orbitbank_api`.

If you encounter issues, check the container logs:

```bash
docker logs orbitbank_api
```

### 5. Access the API

The API is now running at `http://localhost:8000`.
Access the interactive API documentation (Swagger UI) at `http://localhost:8000/docs`.
Test endpoints using tools like Postman or cURL, ensuring you include a valid JWT token for authenticated endpoints.

**Note:** For testing, you may need to register a user (`POST /users/register`) and obtain a JWT token via the authentication endpoint (not detailed in the provided overview but typically `POST /auth/login`).

## API Documentation

The API provides a comprehensive set of endpoints for banking operations. Key endpoint groups include:

-   User Management: `/users/register`, `/users/me`, `/users/{user_id}/change-password`
-   Account Management: `/accounts/{account_id}/balance`, `/accounts/{account_id}/deposit`, `/accounts/{account_id}/statement`
-   Transfer Management: `/transfers/new`
-   Supporting Services: `/transactions`, `/banks`, `/branches`, `/account-types`
-   Notification Testing: `/verify/verify-email-identity`, `/verify/initiate-sandbox-phone-verification`

For detailed endpoint descriptions, refer to the API Overview or explore the Swagger UI at `http://localhost:8000/docs`.

## Testing

To test the application:

-   Use the Swagger UI (`/docs`) for manual testing of endpoints.
-   Write automated tests using Pytest (if test files are included in the repository).
-   Simulate transactions and notifications using the sandbox endpoints for AWS SES/SNS.
-   Verify database consistency by checking PostgreSQL tables after operations.

**Note:** Ensure your AWS SES and SNS services are in sandbox mode or fully verified to avoid delivery issues during testing.

## Deployment

The application is configured for deployment to AWS EC2 with a CI/CD pipeline using GitHub Actions and AWS ECR. To deploy manually:

1.  Push the Docker image to an AWS ECR repository.
2.  Configure an EC2 instance with Docker and Docker Compose.
3.  Pull and run the image using the provided `docker-compose.yml`.
4.  Ensure the EC2 security group allows inbound traffic on port 8000.

For details on the CI/CD pipeline, refer to the `.github/workflows/ci-cd.yml` file.

## Contributing

Contributions are welcome! To contribute:

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/your-feature`).
3.  Commit your changes (`git commit -m "Add your feature"`).
4.  Push to the branch (`git push origin feature/your-feature`).
5.  Open a pull request.

Please ensure your code follows the project’s coding standards and includes relevant tests.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
