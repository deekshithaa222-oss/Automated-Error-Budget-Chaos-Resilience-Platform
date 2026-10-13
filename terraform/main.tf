terraform {
  required_version = ">= 1.5.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.31"
    }
  }
}

provider "kubernetes" {
  config_path = var.kubeconfig_path
}

variable "kubeconfig_path" {
  type        = string
  description = "Path to the kubeconfig for a local kind or minikube cluster."
  default     = "~/.kube/config"
}

resource "kubernetes_namespace" "chaosgate" {
  metadata {
    name = "chaosgate"
  }
}

output "namespace" {
  value = kubernetes_namespace.chaosgate.metadata[0].name
}

