from backend import orliq_admin_routes
from backend.db import SessionLocal
from backend.models import User


def test_orliq_admin_lists_and_suspends_user(client, monkeypatch):
    monkeypatch.setattr(orliq_admin_routes, 'ORLIQ_ADMIN_API_KEY', 'x' * 40)
    headers={'X-ORLIQ-ADMIN-KEY':'x' * 40}
    response=client.get('/api/orliq-admin/users', headers=headers)
    assert response.status_code == 200
    item=response.json()['items'][0]
    assert item['email'] == 'test@example.com'
    assert item['is_active'] is True

    response=client.patch(f"/api/orliq-admin/users/{item['id']}", headers=headers, json={'is_active':False})
    assert response.status_code == 400  # bootstrap admin cannot be suspended

    with SessionLocal() as db:
        other=User(email='other@example.com',password_hash='!',name='Outro',email_verified_at=1)
        db.add(other); db.commit(); db.refresh(other)
        other_id=other.id
    response=client.patch(f'/api/orliq-admin/users/{other_id}', headers=headers, json={'is_active':False})
    assert response.status_code == 200
    assert response.json()['is_active'] is False
