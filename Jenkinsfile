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
