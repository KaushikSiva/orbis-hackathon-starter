"""Share only the recipient frozen into an approved export; preserve uncertain outcomes."""
from fastapi import HTTPException


def existing_access(permissions, recipient, user_id=None):
    for entry in permissions.get('data', []):
        emails = [entry.get(key) for key in ('primary_email', 'workspace_email', 'guest_email')]
        if (user_id and entry.get('user_id') == user_id) or any(isinstance(email, str) and email.casefold() == recipient.casefold() for email in emails):
            return 'shared'
    if any(entry.get('email', '').casefold() == recipient.casefold() for entry in permissions.get('pending', [])):
        return 'pending'
    return None


async def share_document(exported, recipient, request, persist):
    """persist() synchronously stores the export and approval before any write."""
    if not recipient or not exported.get('verified'):
        return
    sharing = exported.setdefault('sharing', {'recipient': recipient, 'role': 'viewer', 'status': 'not_started'})
    if sharing['recipient'] != recipient:
        raise RuntimeError('Sharing recipient differs from the approved preview')
    if sharing['status'] == 'shared':
        return
    path = f"/api/documents/{exported['id']}"
    # Read first: an earlier timed-out invitation may already exist or be accepted.
    try:
        permissions = await request('ambiguous', 'GET', path + '/permissions')
    except HTTPException:
        if sharing['status'] not in ('in_flight', 'uncertain', 'unverified', 'pending'):
            sharing['status'] = 'failed'
        sharing['message'] = 'The document is saved. Sharing could not be checked; try checking again.'
        persist()
        return
    status = existing_access(permissions, recipient, sharing.get('user_id'))
    if status:
        sharing.update(status=status, message=('Accept the Ambiguous invitation sent to this address.' if status == 'pending' else 'Document access is confirmed.'))
        persist()
        return
    if sharing['status'] in ('in_flight', 'uncertain', 'unverified', 'pending'):
        sharing.update(status='uncertain', message='The document is saved, but the invitation outcome is unclear. Check your Ambiguous inbox; another invitation has not been sent.')
        persist()
        return
    sharing.update(status='in_flight', message='Sending the document invitation.')
    persist()
    try:
        result = await request('ambiguous', 'POST', path + '/share-invite', json={'email': recipient, 'role': 'viewer', 'invite_to_workspace': False})
    except HTTPException as exc:
        upstream = getattr(exc, 'upstream_status', None)
        rejected = 400 <= upstream < 500 and upstream not in (408, 425) if upstream else exc.status_code in (429, 503)
        sharing.update(status='failed' if rejected else 'uncertain', message=('The document is saved, but sharing was rejected. Retry sharing.' if rejected else 'The document is saved, but the invitation outcome is unclear. Check sharing before retrying.'))
        persist()
        return
    sharing.update(status='unverified', user_id=result.get('user_id'), pending_share_id=result.get('pending_share_id'), invite_id=result.get('invite_id'))
    persist()
    try:
        permissions = await request('ambiguous', 'GET', path + '/permissions')
        status = existing_access(permissions, recipient, sharing.get('user_id'))
    except HTTPException:
        status = None
    sharing.update(status=status or 'unverified', message=('Accept the Ambiguous invitation sent to this address.' if status == 'pending' else 'Document access is confirmed.' if status == 'shared' else 'The invitation was requested; access has not yet been verified. Check sharing again.'))
    persist()
