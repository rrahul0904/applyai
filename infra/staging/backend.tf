terraform {
  backend "s3" {
    key          = "applyai/staging/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}
