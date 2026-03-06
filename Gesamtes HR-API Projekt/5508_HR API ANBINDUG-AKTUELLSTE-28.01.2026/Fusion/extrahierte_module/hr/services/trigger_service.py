"""
Trigger-Service: Trigger-Auswertung, E-Mail- und API-Aktionen.

Quelle: app.py Zeilen 1164-1835 (TriggerEngine, EmailAction, APIAction)

ANPASSUNG gegenüber HR-Hub:
- Kein TriggerStore/TriggerLogStore (JSON-basiert) mehr
- Trigger-Config und Logs kommen/gehen über den API-Client
- TriggerEngine bekommt Trigger-Liste und SMTP-Config als Parameter
"""

import json
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)


class TriggerEngine:
    """
    Engine zur Auswertung von Triggern und Ausführung von Aktionen.

    Wird beim Delta-Export aufgerufen und prüft:
    1. Welche Trigger für den Arbeitgeber aktiv sind
    2. Welche Events eingetreten sind
    3. Ob die Bedingungen erfüllt sind
    4. Führt die Aktionen aus (E-Mail, API)

    Quelle: app.py Zeilen 1164-1600
    """

    def evaluate_and_execute(self, employer_cfg: dict, diff: dict,
                             current_data: dict, triggers: list[dict],
                             smtp_config: dict = None,
                             executed_by: str = 'system') -> list[dict]:
        """
        Wertet alle Trigger aus und führt passende Aktionen aus.

        Args:
            employer_cfg: Arbeitgeber-Konfiguration
            diff: Diff-Objekt mit 'added', 'removed', 'changed'
            current_data: Aktuelle Mitarbeiter-Daten {pid: data}
            triggers: Liste aktiver Trigger-Definitionen (aus DB)
            smtp_config: SMTP-Konfiguration für E-Mail-Versand
            executed_by: Ausführender Benutzer

        Returns:
            Liste der Ausführungsergebnisse
        """
        employer_id = employer_cfg.get('id')
        employer_name = employer_cfg.get('name', '')
        results = []

        if not triggers:
            return results

        for trigger in triggers:
            try:
                event = trigger.get('event', 'employee_changed')
                affected_employees = []

                if event == 'employee_added' and diff.get('added'):
                    affected_employees = self._process_added_employees(
                        diff['added'], current_data, trigger
                    )
                elif event == 'employee_removed' and diff.get('removed'):
                    affected_employees = self._process_removed_employees(
                        diff['removed'], trigger
                    )
                elif event == 'employee_changed' and diff.get('changed'):
                    affected_employees = self._process_changed_employees(
                        diff['changed'], current_data, trigger
                    )

                if not affected_employees:
                    continue

                action_type = trigger.get('action', {}).get('type', 'email')
                action_config = trigger.get('action', {}).get('config', {})
                send_individual = action_config.get('send_individual', True)

                if send_individual and len(affected_employees) > 1:
                    for emp in affected_employees:
                        context = self._build_context(
                            employer_cfg, trigger, [emp], current_data
                        )
                        success, action_details, error_message = self._execute_action(
                            action_type, action_config, context, smtp_config
                        )
                        results.append({
                            'trigger_id': trigger.get('id'),
                            'trigger_name': trigger.get('name'),
                            'event': event,
                            'employer_id': employer_id,
                            'employer_name': employer_name,
                            'affected_employees': [emp],
                            'action_type': action_type,
                            'action_details': action_details,
                            'status': 'success' if success else 'error',
                            'error_message': error_message,
                            'executed_by': executed_by,
                            'employee_pid': emp.get('personId'),
                            'employee_name': f"{emp.get('firstName', '')} {emp.get('lastName', '')}".strip()
                        })
                else:
                    context = self._build_context(
                        employer_cfg, trigger, affected_employees, current_data
                    )
                    success, action_details, error_message = self._execute_action(
                        action_type, action_config, context, smtp_config
                    )
                    results.append({
                        'trigger_id': trigger.get('id'),
                        'trigger_name': trigger.get('name'),
                        'event': event,
                        'employer_id': employer_id,
                        'employer_name': employer_name,
                        'affected_employees': affected_employees,
                        'action_type': action_type,
                        'action_details': action_details,
                        'status': 'success' if success else 'error',
                        'error_message': error_message,
                        'executed_by': executed_by,
                    })

            except Exception as e:
                logger.error(f"Fehler bei Trigger '{trigger.get('name')}': {e}")
                results.append({
                    'trigger_id': trigger.get('id'),
                    'trigger_name': trigger.get('name'),
                    'event': trigger.get('event', 'unknown'),
                    'employer_id': employer_id,
                    'employer_name': employer_name,
                    'affected_employees': [],
                    'action_type': trigger.get('action', {}).get('type', 'unknown'),
                    'action_details': {},
                    'status': 'error',
                    'error_message': str(e),
                    'executed_by': executed_by,
                })

        return results

    def _process_added_employees(self, added_list, current_data, trigger):
        affected = []
        for emp in added_list:
            pid = emp.get('pid')
            emp_data = current_data.get(pid, {}).get('core', {})
            affected.append({
                'personId': pid,
                'firstName': emp_data.get('Vorname', emp.get('name', '').split()[0] if emp.get('name') else ''),
                'lastName': emp_data.get('Name', emp.get('name', '').split()[-1] if emp.get('name') else ''),
                'data': emp_data,
                'changes': []
            })
        return affected

    def _process_removed_employees(self, removed_list, trigger):
        affected = []
        for emp in removed_list:
            name_parts = emp.get('name', '').split()
            affected.append({
                'personId': emp.get('pid'),
                'firstName': name_parts[0] if name_parts else '',
                'lastName': name_parts[-1] if len(name_parts) > 1 else '',
                'data': {},
                'changes': []
            })
        return affected

    def _process_changed_employees(self, changed_list, current_data, trigger):
        conditions = trigger.get('conditions', [])
        condition_logic = trigger.get('condition_logic', 'AND')
        affected = []

        for emp in changed_list:
            pid = emp.get('pid')
            changes = emp.get('changes', [])
            if not changes:
                continue

            if conditions:
                matches = [self._check_condition(c, changes) for c in conditions]
                if condition_logic == 'AND' and not all(matches):
                    continue
                elif condition_logic == 'OR' and not any(matches):
                    continue

            emp_data = current_data.get(pid, {}).get('core', {})
            affected.append({
                'personId': pid,
                'firstName': emp_data.get('Vorname', ''),
                'lastName': emp_data.get('Name', ''),
                'data': emp_data,
                'changes': changes
            })

        return affected

    def _check_condition(self, condition, changes):
        field = condition.get('field')
        operator = condition.get('operator')
        from_value = condition.get('from_value') or ''
        to_value = condition.get('to_value') or ''

        change = None
        for c in changes:
            if c.get('field') == field:
                change = c
                break

        if not change and operator not in ('is_empty', 'is_not_empty'):
            return False

        safe_str = lambda val: str(val) if val is not None else ''

        if operator == 'changed':
            return change is not None
        elif operator == 'changed_to':
            return change is not None and safe_str(change.get('new', '')).lower() == safe_str(to_value).lower()
        elif operator == 'changed_from':
            return change is not None and safe_str(change.get('old', '')).lower() == safe_str(from_value).lower()
        elif operator == 'changed_from_to':
            return (change is not None and
                    safe_str(change.get('old', '')).lower() == safe_str(from_value).lower() and
                    safe_str(change.get('new', '')).lower() == safe_str(to_value).lower())
        elif operator == 'is_empty':
            return change is not None and not change.get('new')
        elif operator == 'is_not_empty':
            return change is not None and change.get('new')
        elif operator == 'contains':
            return (change is not None and to_value and
                    safe_str(to_value).lower() in safe_str(change.get('new', '')).lower())
        return False

    def _build_context(self, employer_cfg, trigger, affected_employees, current_data):
        context = {
            '_employerId': employer_cfg.get('id'),
            '_employerName': employer_cfg.get('name'),
            '_triggerName': trigger.get('name'),
            '_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '_employeeCount': len(affected_employees),
            '_employees': affected_employees
        }

        if len(affected_employees) == 1:
            emp = affected_employees[0]
            context.update(emp.get('data', {}))
            if emp.get('changes'):
                first_change = emp['changes'][0]
                context['_changedField'] = first_change.get('field', '')
                context['_oldValue'] = first_change.get('old', '')
                context['_newValue'] = first_change.get('new', '')
            all_changes = []
            for c in emp.get('changes', []):
                all_changes.append(f"{c.get('field')}: {c.get('old', '-')} → {c.get('new', '-')}")
            context['_allChanges'] = '\n'.join(all_changes)

        return context

    def _execute_action(self, action_type, action_config, context, smtp_config=None):
        try:
            if action_type == 'email':
                return EmailAction().execute(action_config, context, smtp_config)
            elif action_type == 'api':
                return APIAction().execute(action_config, context)
            else:
                return False, {}, f"Unbekannter Aktionstyp: {action_type}"
        except Exception as e:
            return False, {}, str(e)


class EmailAction:
    """
    Handler für E-Mail-Aktionen mit Mustache-Template-Rendering.

    Quelle: app.py Zeilen 1602-1740
    """

    def execute(self, config, context, smtp_config):
        if not smtp_config or not smtp_config.get('host'):
            return False, {}, "SMTP nicht konfiguriert"

        recipients = config.get('recipients', [])
        if not recipients:
            return False, {}, "Keine Empfänger angegeben"

        subject = self._render_template(config.get('subject', ''), context)
        body = self._render_template(config.get('body', ''), context)

        try:
            import smtplib
            import socket
            from email.message import EmailMessage

            msg = EmailMessage()
            from_email = smtp_config.get('from_email', smtp_config.get('username', ''))
            msg['From'] = from_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            msg.set_content(body)

            local_hostname = 'localhost'
            try:
                hostname = socket.gethostname()
                hostname.encode('ascii')
                local_hostname = hostname
            except (UnicodeEncodeError, socket.error):
                local_hostname = 'localhost'

            if smtp_config.get('use_tls', True):
                server = smtplib.SMTP(
                    smtp_config['host'], smtp_config.get('port', 587),
                    local_hostname=local_hostname
                )
                server.starttls()
            else:
                server = smtplib.SMTP(
                    smtp_config['host'], smtp_config.get('port', 25),
                    local_hostname=local_hostname
                )

            if smtp_config.get('username') and smtp_config.get('password'):
                server.login(smtp_config['username'], smtp_config['password'])

            server.send_message(msg)
            server.quit()

            return True, {'recipients': recipients, 'subject': subject}, None

        except Exception as e:
            return False, {'recipients': recipients, 'subject': subject}, str(e)

    def _render_template(self, template, context):
        if not template:
            return ''

        try:
            import chevron
            return chevron.render(template, context)
        except ImportError:
            pass

        result = template
        for key, value in context.items():
            if not key.startswith('_employees'):
                result = result.replace('{{' + key + '}}', str(value or ''))

        if '{{#_employees}}' in result and '{{/_employees}}' in result:
            start = result.find('{{#_employees}}')
            end = result.find('{{/_employees}}')
            if start != -1 and end != -1:
                before = result[:start]
                template_part = result[start + 15:end]
                after = result[end + 15:]
                employees = context.get('_employees', [])
                rendered_parts = []
                for emp in employees:
                    emp_context = dict(context)
                    emp_context.update(emp.get('data', {}))
                    emp_context['firstName'] = emp.get('firstName', '')
                    emp_context['lastName'] = emp.get('lastName', '')
                    emp_context['personId'] = emp.get('personId', '')
                    if emp.get('changes'):
                        emp_context['_changedField'] = emp['changes'][0].get('field', '')
                        emp_context['_oldValue'] = emp['changes'][0].get('old', '')
                        emp_context['_newValue'] = emp['changes'][0].get('new', '')
                    part = template_part
                    for k, v in emp_context.items():
                        part = part.replace('{{' + k + '}}', str(v or ''))
                    rendered_parts.append(part)
                result = before + ''.join(rendered_parts) + after

        return result


class APIAction:
    """
    Handler für API-Aktionen (HTTP-Requests).

    Quelle: app.py Zeilen 1742-1835
    """

    def execute(self, config, context):
        url = self._render_template(config.get('url', ''), context)
        method = config.get('method', 'POST').upper()
        timeout = config.get('timeout_seconds', 30)

        if not url:
            return False, {}, "Keine URL angegeben"

        headers = {'Content-Type': 'application/json'}
        for key, value in config.get('headers', {}).items():
            headers[key] = self._render_template(value, context)

        auth = config.get('auth', {})
        auth_type = auth.get('type', 'none')
        if auth_type == 'bearer' and auth.get('token'):
            headers['Authorization'] = f"Bearer {auth['token']}"
        elif auth_type == 'api_key' and auth.get('api_key'):
            header_name = auth.get('api_key_header', 'X-API-Key')
            headers[header_name] = auth['api_key']

        auth_tuple = None
        if auth_type == 'basic' and auth.get('username'):
            auth_tuple = (auth['username'], auth.get('password', ''))

        body = None
        if method in ['POST', 'PUT', 'PATCH']:
            body_template = config.get('body', '')
            if body_template:
                body_str = self._render_template(body_template, context)
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    body = body_str

        try:
            response = requests.request(
                method=method, url=url, headers=headers,
                json=body if isinstance(body, dict) else None,
                data=body if isinstance(body, str) else None,
                auth=auth_tuple, timeout=timeout
            )
            success = response.status_code < 400
            return success, {
                'url': url, 'method': method,
                'status_code': response.status_code,
                'response_text': response.text[:500] if response.text else ''
            }, None if success else f"HTTP {response.status_code}: {response.text[:200]}"

        except requests.Timeout:
            return False, {'url': url, 'method': method}, f"Timeout nach {timeout} Sekunden"
        except Exception as e:
            return False, {'url': url, 'method': method}, str(e)

    def _render_template(self, template, context):
        if not template:
            return ''
        result = template
        for key, value in context.items():
            if not isinstance(value, (list, dict)):
                result = result.replace('{{' + key + '}}', str(value or ''))
        return result
