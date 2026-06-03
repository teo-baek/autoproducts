def approve_account(repo, target_id: str, admin_id: str) -> dict:
    return repo.set_status(target_id, "approved", admin_id)

def reject_account(repo, target_id: str, admin_id: str) -> dict:
    return repo.set_status(target_id, "rejected", admin_id)
