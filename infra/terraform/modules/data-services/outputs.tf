# -----------------------------------------------------------------------------
# CONTRACT: data-services module outputs.
# RESERVED -- see variables.tf in this directory.
# -----------------------------------------------------------------------------

output "postgres_connection_string" {
  description = "Connection string for the managed PostgreSQL instance (introduced Milestone 3)."
  value       = null
  sensitive   = true
}

output "redis_connection_string" {
  description = "Connection string for the managed Redis instance (introduced Milestone 3)."
  value       = null
  sensitive   = true
}
