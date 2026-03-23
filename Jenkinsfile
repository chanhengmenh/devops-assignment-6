pipeline {
    agent any

    environment {
        SONAR_HOME = tool 'sonar'
        IMAGE_NAME  = "devsecops-api"
        IMAGE_TAG   = "latest"
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

    }
}
