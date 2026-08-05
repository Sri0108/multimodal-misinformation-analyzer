pipeline {
    agent any

    environment {
        BACKEND_IMAGE = "sri0108/misinformation-backend"
        FRONTEND_IMAGE = "sri0108/misinformation-frontend"
        IMAGE_TAG = "${BUILD_NUMBER}"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Environment') {
            steps {
                sh 'whoami'
                sh 'git --version'
                sh 'docker --version'
                sh 'kubectl version --client'
                sh 'helm version'
                sh 'python3 --version'
            }
        }

        stage('Build Backend Image') {
            steps {
                sh '''
                docker build \
                  -t ${BACKEND_IMAGE}:${IMAGE_TAG} \
                  -f docker/backend/Dockerfile \
                  .
                '''
            }
        }

        stage('Build Frontend Image') {
            steps {
                sh '''
                docker build \
                  -t ${FRONTEND_IMAGE}:${IMAGE_TAG} \
                  -f docker/frontend/Dockerfile \
                  .
                '''
            }
        }

        stage('Verify Images') {
            steps {
                sh '''
                docker images | grep misinformation
                '''
            }
        }

    }

    post {
        success {
            echo "Images built successfully."
        }

        failure {
            echo "Pipeline failed."
        }
    }
}