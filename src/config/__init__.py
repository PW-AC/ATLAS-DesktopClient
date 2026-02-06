"""
Konfigurationsmodul fuer BiPRO-GDV Tool.
"""

from .processing_rules import PROCESSING_RULES
from .certificates import get_certificate_manager, CertificateInfo, CertificateManager
from .vu_endpoints import (
    get_vu_endpoint_manager, VUEndpointConfig, VUEndpointManager,
    KNOWN_ENDPOINTS, AUTH_TYPE_PASSWORD, AUTH_TYPE_CERT_WS, 
    AUTH_TYPE_CERT_TGIC, AUTH_TYPE_CERT_DEGENIA, AUTH_TYPE_LABELS
)
from .smartadmin_endpoints import (
    SMARTADMIN_COMPANIES, SmartAdminCompany, ServiceEndpoint, AuthType,
    get_company_by_name, get_all_companies, get_companies_by_auth_type,
    get_easylogin_companies
)

__all__ = [
    'PROCESSING_RULES',
    'get_certificate_manager', 'CertificateInfo', 'CertificateManager',
    'get_vu_endpoint_manager', 'VUEndpointConfig', 'VUEndpointManager',
    'KNOWN_ENDPOINTS', 'AUTH_TYPE_PASSWORD', 'AUTH_TYPE_CERT_WS',
    'AUTH_TYPE_CERT_TGIC', 'AUTH_TYPE_CERT_DEGENIA', 'AUTH_TYPE_LABELS',
    # SmartAdmin
    'SMARTADMIN_COMPANIES', 'SmartAdminCompany', 'ServiceEndpoint', 'AuthType',
    'get_company_by_name', 'get_all_companies', 'get_companies_by_auth_type',
    'get_easylogin_companies'
]
