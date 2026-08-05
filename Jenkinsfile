pipeline {
    agent any

    environment {
        BACKEND_IMAGE = "srikandala/misinformation-backend"
        FRONTEND_IMAGE = "srikandala/misinformation-frontend"
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
                 docker image inspect ${BACKEND_IMAGE}:${IMAGE_TAG}
                 docker image inspect ${FRONTEND_IMAGE}:${IMAGE_TAG}
                '''
            }
        }

        stage('Docker Login') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-creds',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {

                    sh '''
                    echo "$DOCKER_PASS" | docker login \
                        -u "$DOCKER_USER" \
                        --password-stdin
                    '''
                }
            }
        }

        stage('Push Backend Image') {
            steps {
                sh '''
                docker push ${BACKEND_IMAGE}:${IMAGE_TAG}
                '''
            }
        }

        stage('Push Frontend Image') {
            steps {
                sh '''
                docker push ${FRONTEND_IMAGE}:${IMAGE_TAG}
                '''
            }
        }
        stage('Deploy to Kubernetes') {
            steps {
                sh '''
                helm upgrade --install misinformation \
                helm/misinformation-analyzer \
                -n devops-lab \
                --set backend.image.repository=${BACKEND_IMAGE} \
                --set backend.image.tag=${IMAGE_TAG} \
                --set frontend.image.repository=${FRONTEND_IMAGE} \
                --set frontend.image.tag=${IMAGE_TAG}
                '''
            }
        }

        stage('Verify Deployment') {
            steps {
                sh '''
                kubectl rollout status deployment/backend -n devops-lab --timeout=600s
                kubectl rollout status deployment/frontend -n devops-lab --timeout=600s

                kubectl get pods -n devops-lab
                '''
            }
        }
    }

    post {
        always {
            sh 'docker logout || true'
        }

        success {
            echo "application deployed successfully."
        }

        failure {
            echo "Pipeline failed."
        }
    }
}