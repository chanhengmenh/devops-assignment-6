# DevSecOps Pipeline — Assignment 6

A full DevSecOps CI/CD pipeline using **Jenkins**, **SonarQube**, **Docker**, and **Trivy** on AWS EC2, deploying a simple Python FastAPI REST API.

---

## Architecture Overview

```
GitHub ──(1)──► Jenkins EC2
                    │
               (2)  │  (3)
                    ▼
              SonarQube EC2 (Docker)
                    │
               (4)  │  (5)
                    ▼
         Trivy Code Scan (Jenkins EC2)
                    │
               (6)  │
                    ▼
         Docker Build Image (Jenkins EC2)
                    │
               (7)  │  (8)
                    ▼
         Trivy Image Scan (Jenkins EC2)
                    │
              (9)   │
                    ▼
         Deploy Container (Jenkins EC2)
                    │
              (10)  │
                    ▼
         Running App on port 5000 ──► Postman
```

| Step | Action | Where |
|------|--------|--------|
| 1 | Pull source code from GitHub | Jenkins EC2 |
| 2 | Send code to SonarQube for analysis | SonarQube EC2 |
| 3 | Receive Quality Gate result | Jenkins EC2 |
| 4-5 | Trivy scans the file system (code) | Jenkins EC2 |
| 6 | Build Docker image from Dockerfile | Jenkins EC2 |
| 7-8 | Trivy scans the Docker image | Jenkins EC2 |
| 9-10 | Deploy and run the container | Jenkins EC2 |

---

## Project File Structure

```
devops-assignment-6/
├── README.md                  ← This guide
├── DevSecOps.png              ← Architecture diagram
├── app.py                     ← FastAPI REST API (your application)
├── requirements.txt           ← Python dependencies
├── Dockerfile                 ← Container build instructions
├── sonar-project.properties   ← SonarQube configuration
└── Jenkinsfile                ← Full CI/CD pipeline script
```

---

## Prerequisites

Before you start, make sure you have:

- [ ] An **AWS account** with permission to create EC2 instances
- [ ] A **GitHub account** with a new repository created
- [ ] **Postman** installed locally (for Task 16)
- [ ] **SSH client** (e.g. Git Bash, PowerShell, or terminal)

---

## Task 1 — Create EC2 Instances

You will create **two** EC2 instances. Both use Ubuntu 22.04 LTS.

### 1.1 Create a Key Pair

1. Go to **AWS Console → EC2 → Key Pairs → Create key pair**
2. Name: `devops-keypair`
3. Key pair type: **RSA**
4. Private key file format: **.pem**
5. Click **Create key pair** — the `.pem` file downloads automatically
6. Save it somewhere safe (e.g. `C:\Users\You\devops-keypair.pem`)

> **Windows only:** right-click the `.pem` file → Properties → Security → Advanced → disable inheritance → add yourself with Read permission.

---

### 1.2 Create the Jenkins EC2 Instance

1. Go to **EC2 → Instances → Launch instances**

| Setting | Value |
|---------|-------|
| Name | `Jenkins-EC2` |
| AMI | Ubuntu Server 22.04 LTS (64-bit x86) |
| Instance type | `t2.medium` (2 vCPU, 4 GB RAM) |
| Key pair | `devops-keypair` |
| Storage | 20 GB gp3 |

2. Under **Network Settings → Edit**, create a new Security Group named `jenkins-sg` with these inbound rules:

| Type | Protocol | Port | Source | Purpose |
|------|----------|------|--------|---------|
| SSH | TCP | 22 | My IP | Remote access |
| Custom TCP | TCP | 8080 | 0.0.0.0/0 | Jenkins Web UI |
| Custom TCP | TCP | 5000 | 0.0.0.0/0 | FastAPI App |

3. Click **Launch instance**

---

### 1.3 Create the SonarQube EC2 Instance

1. Go to **EC2 → Instances → Launch instances**

| Setting | Value |
|---------|-------|
| Name | `SonarQube-EC2` |
| AMI | Ubuntu Server 22.04 LTS (64-bit x86) |
| Instance type | `t2.medium` (2 vCPU, 4 GB RAM) |
| Key pair | `devops-keypair` |
| Storage | 20 GB gp3 |

2. Create a new Security Group named `sonarqube-sg`:

| Type | Protocol | Port | Source | Purpose |
|------|----------|------|--------|---------|
| SSH | TCP | 22 | My IP | Remote access |
| Custom TCP | TCP | 9000 | 0.0.0.0/0 | SonarQube Web UI |

3. Click **Launch instance**

> Wait until both instances show **"Running"** status before proceeding.

---

## Task 2 — Install Jenkins on Jenkins EC2

### 2.1 SSH into Jenkins EC2

```bash
# From your local machine
ssh -i "devops-keypair.pem" ubuntu@<JENKINS_EC2_PUBLIC_IP>
```

---

### 2.2 Install Java (Jenkins requires Java 17+)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y openjdk-17-jdk
java -version
```

Expected output: `openjdk version "17.x.x"`

---

### 2.3 Install Jenkins

```bash
# Add Jenkins repository key
sudo wget -O /usr/share/keyrings/jenkins-keyring.asc \
  https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key

# Add Jenkins apt repository
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] \
  https://pkg.jenkins.io/debian-stable binary/" | \
  sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

# Install Jenkins
sudo apt update
sudo apt install -y jenkins

# Start and enable Jenkins service
sudo systemctl start jenkins
sudo systemctl enable jenkins
sudo systemctl status jenkins
```

You should see **"active (running)"** in green.

---

### 2.4 Install Docker on Jenkins EC2

Jenkins will use Docker to build and run containers.

```bash
# Install prerequisites
sudo apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# Add ubuntu and jenkins users to the docker group
sudo usermod -aG docker ubuntu
sudo usermod -aG docker jenkins

# Apply group changes and restart services
sudo systemctl restart docker
sudo systemctl restart jenkins

# Verify
docker --version
```

---

### 2.5 Install Trivy on Jenkins EC2

```bash
sudo apt install -y wget apt-transport-https gnupg

wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | \
  sudo gpg --dearmor -o /usr/share/keyrings/trivy.gpg

echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] \
  https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | \
  sudo tee /etc/apt/sources.list.d/trivy.list

sudo apt update
sudo apt install -y trivy

# Verify
trivy --version
```

---

### 2.6 Get the Initial Jenkins Admin Password

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Copy this password — you need it to unlock Jenkins in the browser.

---

### 2.7 Set Up Jenkins in the Browser

1. Open: `http://<JENKINS_EC2_PUBLIC_IP>:8080`
2. Paste the initial admin password
3. Click **"Install suggested plugins"** and wait for them to install
4. Create your admin account (fill in username, password, email)
5. Set Jenkins URL: `http://<JENKINS_EC2_PUBLIC_IP>:8080`
6. Click **"Save and Finish"**

---

### 2.8 Install Additional Jenkins Plugins

Go to **Manage Jenkins → Plugins → Available plugins**, search and install each of the following (check the box, then click **Install**):

| Plugin Name | Purpose |
|-------------|---------|
| SonarQube Scanner | SonarQube integration |
| Docker Pipeline | Docker commands in pipeline |
| Docker Commons | Shared Docker utilities |
| Blue Ocean *(optional)* | Better pipeline UI |

After installing, click **"Restart Jenkins when no jobs are running"**.

---

## Task 3 — Pull and Run SonarQube Docker Image

### 3.1 SSH into SonarQube EC2

```bash
# Open a NEW terminal window
ssh -i "devops-keypair.pem" ubuntu@<SONARQUBE_EC2_PUBLIC_IP>
```

---

### 3.2 Install Docker on SonarQube EC2

Run the same Docker installation commands from **Task 2.4** above (on this EC2):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io
sudo usermod -aG docker ubuntu
sudo systemctl restart docker
docker --version
```

---

### 3.3 Fix Elasticsearch Memory Limit

SonarQube uses Elasticsearch internally. Without this fix, the container will crash.

```bash
# Apply temporarily (takes effect immediately)
sudo sysctl -w vm.max_map_count=262144

# Apply permanently (survives reboots)
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

---

### 3.4 Run the SonarQube Docker Container

```bash
docker run -d \
  --name sonarqube \
  --restart unless-stopped \
  -p 9000:9000 \
  -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true \
  sonarqube:lts-community
```

Verify it is running:

```bash
docker ps
docker logs sonarqube --follow
```

Wait until you see `SonarQube is operational` in the logs (can take 1–2 minutes).

---

### 3.5 Access SonarQube in the Browser

1. Open: `http://<SONARQUBE_EC2_PUBLIC_IP>:9000`
2. Default login: **admin / admin**
3. You will be prompted to change the password — do so and save your new password

> **Screenshot** — Take a screenshot of the SonarQube dashboard after login.

---

## Task 4 — Create SonarQube Webhook (to notify Jenkins)

1. In SonarQube, go to **Administration → Configuration → Webhooks**
2. Click **Create**
3. Fill in:
   - **Name:** `Jenkins`
   - **URL:** `http://<JENKINS_EC2_PUBLIC_IP>:8080/sonarqube-webhook/`
   - **Secret:** *(leave blank)*
4. Click **Create**

> The trailing slash `/` in the webhook URL is **required**.

> **Screenshot** — Show the webhook entry in SonarQube.

---

## Task 5 — Configure Jenkins to Communicate with SonarQube

### 5.1 Generate a SonarQube Token

1. In SonarQube, click your **user avatar (top right) → My Account**
2. Go to the **Security** tab
3. Under **"Generate Tokens"**:
   - **Name:** `jenkins-token`
   - **Type:** `Global Analysis Token`
   - **Expires:** *(No expiration — or set one)*
4. Click **Generate**
5. **Copy the token immediately** — it is shown only once

---

### 5.2 Add the SonarQube Token to Jenkins Credentials

1. In Jenkins, go to **Manage Jenkins → Credentials → System → Global credentials → Add Credentials**
2. Fill in:
   - **Kind:** Secret text
   - **Secret:** *(paste the token you copied)*
   - **ID:** `sonar-token`
   - **Description:** SonarQube Token
3. Click **Create**

---

### 5.3 Configure SonarQube Server in Jenkins

1. Go to **Manage Jenkins → System**
2. Scroll to the **"SonarQube servers"** section
3. Check **"Environment variables"** checkbox
4. Click **Add SonarQube**:
   - **Name:** `sonar`  ← must match `withSonarQubeEnv('sonar')` in Jenkinsfile
   - **Server URL:** `http://<SONARQUBE_EC2_PUBLIC_IP>:9000`
   - **Server authentication token:** select `sonar-token`
5. Click **Save**

---

## Task 6 — Configure SonarQube Scanner Inside Jenkins

1. Go to **Manage Jenkins → Tools**
2. Scroll to **"SonarQube Scanner installations"**
3. Click **Add SonarQube Scanner**:
   - **Name:** `sonar`  ← must match `tool 'sonar'` in Jenkinsfile
   - Check **"Install automatically"**
   - Version: select the latest
4. Click **Save**

---

## Task 7 — Push Your Project Code to GitHub

### 7.1 Create a GitHub Repository

1. Go to github.com → **New repository**
2. Name: `devops-assignment-6`
3. Visibility: Public (or Private)
4. **Do NOT** initialize with README (you already have files)
5. Click **Create repository**

---

### 7.2 Push Your Local Code

Run these commands from your **local machine** inside the project folder:

```bash
git init
git add .
git commit -m "Initial commit: DevSecOps pipeline project"
git branch -M main
git remote add origin https://github.com/chanhengmenh/devops-assignment-6.git
git push -u origin main
```

Verify: refresh your GitHub repo page — all files should be visible.

---

## Task 8 — Write Declarative Pipeline Script (SonarQube + Quality Gate)

This is the **first version** of the Jenkinsfile — it only has the SonarQube stages.

> The complete final `Jenkinsfile` already exists in your repository.
> For Task 8, you are only using the first 3 stages. Below is that minimal version for reference.

### Minimal Jenkinsfile for Task 8

```groovy
pipeline {
    agent any

    environment {
        SONAR_HOME = tool 'sonar'
    }

    stages {

        stage('Clone Code from GitHub') {
            steps {
                git url: 'https://github.com/chanhengmenh/devops-assignment-6.git',
                    branch: 'main'
            }
        }

        stage('SonarQube: Code Analysis') {
            steps {
                withSonarQubeEnv('sonar') {
                    sh '''
                        $SONAR_HOME/bin/sonar-scanner \
                            -Dsonar.projectKey=devsecops-api \
                            -Dsonar.projectName="DevSecOps API" \
                            -Dsonar.sources=. \
                            -Dsonar.exclusions=**/__pycache__/**,**/*.html
                    '''
                }
            }
        }

        stage('SonarQube: Quality Gate') {
            steps {
                timeout(time: 2, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: false
                }
            }
        }

    }
}
```

> **Screenshot** — Take a full screenshot of the Jenkinsfile script above inside Jenkins.

---

### Create the Jenkins Pipeline Job

1. In Jenkins, click **"+ New Item"**
2. Name it `DevSecOps-Pipeline`
3. Select **Pipeline** → Click **OK**
4. Under **Pipeline** section:
   - **Definition:** Pipeline script from SCM
   - **SCM:** Git
   - **Repository URL:** `https://github.com/chanhengmenh/devops-assignment-6.git`
   - **Branch:** `*/main`
   - **Script Path:** `Jenkinsfile`
5. Click **Save**

---

## Task 9 — Manually Build and Check

1. On the `DevSecOps-Pipeline` job page, click **"Build Now"**
2. Watch the build progress in the **"Stage View"** or **Blue Ocean** view
3. Click on the build number → **Console Output** to see logs

Expected: All 3 stages should show a green checkmark.

> **Screenshot** — Capture the Stage View showing all stages passing (green).

---

## Task 10 — View SonarQube Report

1. After a successful build, go to your SonarQube dashboard
2. You should see `devsecops-api` project appear
3. Click on it to view the report

Key metrics to check:
- **Bugs** — logical errors
- **Vulnerabilities** — security issues
- **Code Smells** — maintainability issues
- **Coverage** — test coverage (will show 0% since no tests are written)
- **Quality Gate Status** — Passed / Failed

> **Screenshot** — Capture the SonarQube project report page showing the metrics and the generated project URL.

---

## Task 11 — Run Trivy File System Scan (Code Scanning)

### Add this stage to your Jenkinsfile

Add the following stage **after** `SonarQube: Quality Gate`:

```groovy
// TASK 11 — Stage 4: Trivy file-system / code scan
stage('Trivy: File System Scan') {
    steps {
        sh 'trivy fs --format table -o trivy-fs-report.html .'
    }
}
```

> **Script Screenshot** — Take a screenshot showing this stage added to the Jenkinsfile.

The `-o trivy-fs-report.html` flag saves the output as an HTML report, which Jenkins archives as a build artifact.

---

## Task 12 — Create Docker Image

### 12.1 Review the Dockerfile

The `Dockerfile` in your repository:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

# uvicorn is the ASGI server that runs FastAPI
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
```

### 12.2 Add the Docker Build Stage to Jenkinsfile

First, add `IMAGE_NAME` and `IMAGE_TAG` to the `environment` block:

```groovy
environment {
    SONAR_HOME  = tool 'sonar'
    IMAGE_NAME  = "devsecops-api"
    IMAGE_TAG   = "latest"
}
```

Then add this stage **after** `Trivy: File System Scan`:

```groovy
// TASK 12 — Stage 5: Build Docker image
stage('Docker: Build Image') {
    steps {
        sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .'
    }
}
```

> **Script Screenshot** — Take a screenshot showing the Dockerfile and this stage in the Jenkinsfile.

---

## Task 13 — Image Scan through Trivy

Add this stage **after** `Docker: Build Image`:

```groovy
// TASK 13 — Stage 6: Trivy image scan
stage('Trivy: Image Scan') {
    steps {
        sh 'trivy image --format table -o trivy-image-report.html ${IMAGE_NAME}:${IMAGE_TAG}'
    }
}
```

> **Script Screenshot** — Take a screenshot showing this stage in the Jenkinsfile.

---

## Task 14 — Deploy Docker Container on EC2

### Add to the `environment` block:

```groovy
CONTAINER_NAME = "devsecops-app"
APP_PORT       = "5000"
```

### Add this stage **after** `Trivy: Image Scan`:

```groovy
// TASK 14 — Stage 7: Deploy container
stage('Docker: Deploy Container') {
    steps {
        sh '''
            docker stop ${CONTAINER_NAME} || true
            docker rm   ${CONTAINER_NAME} || true
            docker run -d \
                --name ${CONTAINER_NAME} \
                -p ${APP_PORT}:5000 \
                ${IMAGE_NAME}:${IMAGE_TAG}
        '''
    }
}
```

Also add the `post` block after `stages`:

```groovy
post {
    always {
        archiveArtifacts artifacts: '*.html', allowEmptyArchive: true
    }
    success {
        echo 'Pipeline completed successfully!'
    }
    failure {
        echo 'Pipeline failed — check the stage logs above.'
    }
}
```

> **Script Screenshot** — Take a screenshot showing this final stage in the Jenkinsfile.

---

## Task 15 — Manually Build the Complete Pipeline

1. In Jenkins, go to `DevSecOps-Pipeline` → click **"Build Now"**
2. All **7 stages** should run in sequence:

```
Clone Code from GitHub
    ↓
SonarQube: Code Analysis
    ↓
SonarQube: Quality Gate
    ↓
Trivy: File System Scan
    ↓
Docker: Build Image
    ↓
Trivy: Image Scan
    ↓
Docker: Deploy Container
```

> **Graph Screenshot** — Capture the Stage View or Blue Ocean pipeline graph showing all 7 stages passing (green).

### Verify the Container is Running

SSH into the Jenkins EC2 and run:

```bash
docker ps
```

You should see `devsecops-app` listed as running on port 5000.

---

## Task 16 — Access Your API Through Postman

Your application is accessible at `http://<JENKINS_EC2_PUBLIC_IP>:5000`

> **Bonus:** FastAPI generates interactive API docs automatically.
> Open `http://<JENKINS_EC2_PUBLIC_IP>:5000/docs` in your browser to see the Swagger UI.

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/api/users` | Get all users |
| GET | `/api/users/{id}` | Get a user by ID |
| POST | `/api/users` | Create a new user |
| DELETE | `/api/users/{id}` | Delete a user |

---

### Postman Test Examples

**1. Health Check**
```
Method:  GET
URL:     http://<JENKINS_EC2_PUBLIC_IP>:5000/
```
Expected response:
```json
{
    "status": "ok",
    "message": "DevSecOps API is running!"
}
```

---

**2. Get All Users**
```
Method:  GET
URL:     http://<JENKINS_EC2_PUBLIC_IP>:5000/api/users
```
Expected response:
```json
{
    "users": [
        {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
        {"id": 2, "name": "Bob",   "email": "bob@example.com",   "role": "user"}
    ],
    "count": 2
}
```

---

**3. Get User by ID**
```
Method:  GET
URL:     http://<JENKINS_EC2_PUBLIC_IP>:5000/api/users/1
```

---

**4. Create a New User**
```
Method:  POST
URL:     http://<JENKINS_EC2_PUBLIC_IP>:5000/api/users
Headers: Content-Type: application/json
Body (raw JSON):
{
    "name": "Charlie",
    "email": "charlie@example.com",
    "role": "user"
}
```
Expected response (201 Created):
```json
{
    "id": 3,
    "name": "Charlie",
    "email": "charlie@example.com",
    "role": "user"
}
```

---

**5. Delete a User**
```
Method:  DELETE
URL:     http://<JENKINS_EC2_PUBLIC_IP>:5000/api/users/3
```

> **Screenshot** — Capture each Postman request showing the URL, method, body (for POST), and the response.

---

## Complete Final Jenkinsfile Reference

```groovy
pipeline {
    agent any

    environment {
        SONAR_HOME     = tool 'sonar'
        IMAGE_NAME     = "devsecops-api"
        IMAGE_TAG      = "latest"
        CONTAINER_NAME = "devsecops-app"
        APP_PORT       = "5000"
    }

    stages {

        stage('Clone Code from GitHub') {
            steps {
                git url: 'https://github.com/chanhengmenh/devops-assignment-6.git',
                    branch: 'main'
            }
        }

        stage('SonarQube: Code Analysis') {
            steps {
                withSonarQubeEnv('sonar') {
                    sh '''
                        $SONAR_HOME/bin/sonar-scanner \
                            -Dsonar.projectKey=devsecops-api \
                            -Dsonar.projectName="DevSecOps API" \
                            -Dsonar.sources=. \
                            -Dsonar.exclusions=**/__pycache__/**,**/*.html
                    '''
                }
            }
        }

        stage('SonarQube: Quality Gate') {
            steps {
                timeout(time: 2, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: false
                }
            }
        }

        stage('Trivy: File System Scan') {
            steps {
                sh 'trivy fs --format table -o trivy-fs-report.html .'
            }
        }

        stage('Docker: Build Image') {
            steps {
                sh 'docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .'
            }
        }

        stage('Trivy: Image Scan') {
            steps {
                sh 'trivy image --format table -o trivy-image-report.html ${IMAGE_NAME}:${IMAGE_TAG}'
            }
        }

        stage('Docker: Deploy Container') {
            steps {
                sh '''
                    docker stop ${CONTAINER_NAME} || true
                    docker rm   ${CONTAINER_NAME} || true
                    docker run -d \
                        --name ${CONTAINER_NAME} \
                        -p ${APP_PORT}:5000 \
                        ${IMAGE_NAME}:${IMAGE_TAG}
                '''
            }
        }

    }

    post {
        always {
            archiveArtifacts artifacts: '*.html', allowEmptyArchive: true
        }
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed — check the stage logs above.'
        }
    }
}
```

---

## Troubleshooting

### SonarQube container keeps restarting
```bash
# Check logs
docker logs sonarqube

# Fix: increase vm.max_map_count
sudo sysctl -w vm.max_map_count=262144
docker restart sonarqube
```

### Jenkins cannot run Docker commands
```bash
# Make sure jenkins user is in the docker group
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
```

### Quality Gate times out
- Verify the SonarQube webhook URL is correct (must end with `/sonarqube-webhook/`)
- Verify port 8080 is reachable from SonarQube EC2 (check Jenkins security group)

### Trivy command not found in Jenkins pipeline
```bash
# Verify Trivy is installed on Jenkins EC2
which trivy
trivy --version
```

### Port 5000 not accessible in Postman
- Check Jenkins EC2 security group allows inbound TCP on port 5000 from `0.0.0.0/0`
- Verify the container is running: `docker ps`

### `waitForQualityGate` step not found
- Make sure the **SonarQube Scanner** plugin is installed and Jenkins has been restarted

---

## Summary of Tools & Versions

| Tool | Version | Where |
|------|---------|--------|
| Ubuntu | 22.04 LTS | Both EC2 instances |
| Java | OpenJDK 17 | Jenkins EC2 |
| Jenkins | LTS | Jenkins EC2 |
| Docker | Latest CE | Both EC2 instances |
| Trivy | Latest | Jenkins EC2 |
| SonarQube | LTS Community | SonarQube EC2 (Docker) |
| Python | 3.11 | Inside Docker container |
| FastAPI | 0.115.6 | Inside Docker container |
| Uvicorn | 0.34.0 | Inside Docker container (ASGI server) |
