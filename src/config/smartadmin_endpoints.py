"""
BiPRO-GDV Tool - SmartAdmin Endpunkte

Vollständige BiPRO-Endpunkte aus dem SmartAdmin/bipro-service.
Enthält 47 Versicherer mit STS-, Transfer- und Extranet-URLs.

Quelle: Smart InsurTech AG bipro-service.jar -> companies.json
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum


class AuthType(Enum):
    """BiPRO Authentifizierungstypen aus SmartAdmin."""
    WEAK = "Weak"                      # Username + Password
    STRONG = "Strong"                  # Username + Password + OTP
    CERTIFICATE = "Certificate"        # X.509 Zertifikat
    TICKET = "Ticket"                  # VDG EasyLogin Ticket
    TICKET_OTP = "TicketOTP"           # Ticket + OTP
    TICKET_CERT = "TicketCertificate"  # Ticket + Zertifikat
    TGIC_CERT = "TGICCertificate"      # TGIC + Zertifikat (Generali-Gruppe)
    TGIC_MTAN = "TGICmTAN"             # TGIC + mTAN


@dataclass
class ServiceEndpoint:
    """Ein einzelner BiPRO-Service-Endpunkt."""
    name: str                          # SecurityTokenService, TransferService, ExtranetService
    url: str
    version: str
    auth_type: Optional[str] = None    # Nur für STS relevant
    vuid: Optional[str] = None         # Versicherer-ID für Extranet
    weak_saml: bool = False            # Spezielle SAML-Variante


@dataclass
class SmartAdminCompany:
    """Versicherer mit allen BiPRO-Endpunkten."""
    name: str
    services: List[ServiceEndpoint] = field(default_factory=list)
    easylogin_vuid: Optional[str] = None  # VDG EasyLogin Identifier
    
    def get_sts_url(self, auth_type: str = None) -> Optional[str]:
        """Gibt die STS-URL zurück, optional gefiltert nach Auth-Typ."""
        for s in self.services:
            if s.name == "SecurityTokenService":
                if auth_type is None or s.auth_type == auth_type:
                    return s.url
        return None
    
    def get_transfer_url(self) -> Optional[str]:
        """Gibt die Transfer-URL zurück."""
        for s in self.services:
            if s.name == "TransferService":
                return s.url
        return None
    
    def get_extranet_url(self) -> Optional[str]:
        """Gibt die Extranet-URL zurück."""
        for s in self.services:
            if s.name == "ExtranetService":
                return s.url
        return None
    
    def get_auth_types(self) -> List[str]:
        """Gibt alle verfügbaren Auth-Typen zurück."""
        return [s.auth_type for s in self.services 
                if s.name == "SecurityTokenService" and s.auth_type]


# =============================================================================
# SMARTADMIN ENDPUNKTE (aus companies.json)
# =============================================================================

SMARTADMIN_COMPANIES: Dict[str, SmartAdminCompany] = {
    "adam_riese": SmartAdminCompany(
        name="Adam Riese",
        services=[
            ServiceEndpoint("SecurityTokenService", "http://www.tgic.de/WVMV/prod/Dokumentenservice_430/1.0", "V2_6_1", "TGICCertificate"),
            ServiceEndpoint("TransferService", "https://pws3009.ww-ag.de:443/BiPro/TransferService_2.6.1.1.0", "V2_6_1"),
        ]
    ),
    "aig": SmartAdminCompany(
        name="AIG",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://wuebanet.de/X4/httpstarter/WS/1/STS/UserPasswordLogin_2.5.0.1.1", "V2_5_0_1_1", "Weak"),
            ServiceEndpoint("TransferService", "https://wuebanet.de/X4/httpstarter/WS/1/BiPRO/TransferService_2.4.2.1.1", "V2_4_2_1_1"),
        ]
    ),
    "allianz": SmartAdminCompany(
        name="Allianz",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://openstsws.allianz.de/sts/4.0/SecurityTokenService_2.1.3.4.0", "V2_1_4", "Certificate"),
            ServiceEndpoint("TransferService", "https://openbiprows.allianz.de/transferservice-bipro-allianz/TransferService_2.1.1.2.0", "V2_1_1_2"),
            ServiceEndpoint("ExtranetService", "https://openbiprows.allianz.de/extranetservice-bipro-allianz/ExtranetService_1.0.1.0/ExtranetService_1.0.1.0", "V1_0_1"),
        ]
    ),
    "alte_leipziger": SmartAdminCompany(
        name="Alte Leipziger",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://www.vermittlerportal.de/Appserver/BiPRO/STS/SecurityTokenService_2.1.4.1.0", "V2_1_4", "Weak"),
            ServiceEndpoint("TransferService", "https://www.vermittlerportal.de/Appserver/BiPRO/STS/430/TransferService_2.1.4.1.0", "V2_1_4"),
            ServiceEndpoint("ExtranetService", "https://www.vermittlerportal.de/Appserver/BiPRO/STS/440/ExtranetService_1.0.1.0", "V1_0_1"),
        ]
    ),
    "assekuranz_service": SmartAdminCompany(
        name="Assekuranz-Service Center",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://bipro.vs-gruppe.de/ibis/services/ASC.UsernamePasswordLogin_2.1.0.1.0", "V2_1_0", "Weak"),
            ServiceEndpoint("TransferService", "https://bipro.vs-gruppe.de/ibis/services/ASC.TransferService_2.4.0.1.1", "V2_4_0_1_1"),
            ServiceEndpoint("ExtranetService", "https://bipro.vs-gruppe.de/ibis/services/ASC.ExtranetService_1.4.1.1", "V1_4_1_1"),
        ]
    ),
    "axa": SmartAdminCompany(
        name="AXA",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://entry.axa.de/sts/services/UsernamePasswordLogin", "V1_1_1", "Weak"),
            ServiceEndpoint("TransferService", "https://esg.axa.de/prod/biprows/TransferService_2.5.0.1.0", "V2_5_0"),
            ServiceEndpoint("ExtranetService", "https://esg.axa.de/prod/biprows/PortalLinksService_1.4.1.0", "V1_4_1"),
        ]
    ),
    "barmenia": SmartAdminCompany(
        name="Barmenia",
        easylogin_vuid="Barmenia",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://ws.barmenia24.de/ibis/services/VDGTicketLogin_2.1.3.1.0", "V2_1_1", "Ticket"),
            ServiceEndpoint("TransferService", "https://ws.barmenia24.de/ibis/services/transferservice_2.5.0.1.0", "V2_5_0"),
            ServiceEndpoint("ExtranetService", "https://ws.barmenia24.de/ibis/services/extranetservice_1.4.1.0", "V1_4_1", vuid="5317"),
        ]
    ),
    "basler": SmartAdminCompany(
        name="Basler Service Gesellschaft",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://bipro.vs-gruppe.de/ibis/services/BSG.UsernamePasswordLogin_2.1.0.1.0", "V2_1_0", "Weak"),
            ServiceEndpoint("TransferService", "https://bipro.vs-gruppe.de/ibis/services/BSG.TransferService_2.4.0.1.1", "V2_4_0_1_1"),
            ServiceEndpoint("ExtranetService", "https://bipro.vs-gruppe.de/ibis/services/BSG.ExtranetService_1.4.1.1", "V1_4_1_1"),
        ]
    ),
    "canada_life": SmartAdminCompany(
        name="Canada Life",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://bipro.canadalife.de/CLEBiPROSecurityTokenService/2.2.0.1.0/SecurityTokenService.svc/UserPasswordLogin", "V2_2_0", "Weak"),
            ServiceEndpoint("TransferService", "https://bipro.canadalife.de/CLEBiPROTransferService/1.1.1.0/TransferService.svc", "V1_1_1"),
        ]
    ),
    "condor": SmartAdminCompany(
        name="Condor",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://webservice.ruv.de/bipro/sts/2.4.0.1.0", "V2_4_0", "Weak"),
            ServiceEndpoint("TransferService", "https://webservice.ruv.de/bipro/TransferService/2.4.4.1.1", "V2_4_4_1_1"),
            ServiceEndpoint("ExtranetService", "https://webservice.ruv.de/bipro/ExtranetService/1.0.1.0", "V1_0_1", vuid="5339"),
        ]
    ),
    "continentale": SmartAdminCompany(
        name="Continentale",
        easylogin_vuid="contactm",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://www2.continentale.de/bipro410-ws/SecurityTokenService_2.1.0.1.0", "V2_1_1", "Ticket"),
            ServiceEndpoint("TransferService", "https://www4.continentale.de/bipro430-ws/services/TransferService_2.5.0.1.0", "V2_5_0"),
            ServiceEndpoint("ExtranetService", "https://www4.continentale.de/bipro440-ws/services/extranetservice_1.4.1.0", "V1_4_1", vuid="4001"),
        ]
    ),
    "dialog_leben": SmartAdminCompany(
        name="Dialog Lebensversicherung",
        easylogin_vuid="dl",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://dialog-leben.softproject.de/X4/httpstarter/WS/BiPRO/410_STS/UserPasswordLogin_2.6.0.1.0", "V2_6_0", "Weak"),
            ServiceEndpoint("SecurityTokenService", "https://dialog-leben.softproject.de/X4/httpstarter/WS/BiPRO/410_STS/X509Login_2.6.0.1.0", "V2_6_0", "Certificate"),
            ServiceEndpoint("TransferService", "https://dialog-leben.softproject.de/X4/httpstarter/WS/BiPRO/430_Transfer/Service_2.6.0.1.0", "V2_6_0"),
        ]
    ),
    "dialog_versicherung": SmartAdminCompany(
        name="Dialog Versicherung",
        services=[
            ServiceEndpoint("SecurityTokenService", "http://www.tgic.de/DIV/prod/TransferService/2.5.0.1.0", "V2_5_0", "TGICCertificate"),
            ServiceEndpoint("TransferService", "https://tgic.generali.de/div/BiproTransferService_2.5.0.1.0", "V2_5_0"),
            ServiceEndpoint("ExtranetService", "https://tgic.generali.de/div/BiproExtranetService_1.0.1.0", "V1_0_1"),
        ]
    ),
    "die_bayerische": SmartAdminCompany(
        name="Die Bayerische",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://www.bbv.de/BiPRO410Web/services/UserPasswordLogin_2.5.0.1.0", "V2_5_0", "Weak"),
            ServiceEndpoint("TransferService", "https://www.bbv.de/BiPRO430Web/services/TransferService_2.5.0.1.0", "V2_5_0"),
        ]
    ),
    "domcura": SmartAdminCompany(
        name="Domcura",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://api.smartinsurtech.de/soap/SecurityTokenService", "V2_6_0", "Weak", weak_saml=True),
            ServiceEndpoint("TransferService", "https://api.smartinsurtech.de/soap/TransferService_2.6.0.1.0", "V2_6_0"),
        ]
    ),
    "easylogin": SmartAdminCompany(
        name="EasyLogin",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://easy-login.vdg-portal.de/VDGAuthPortal/services/STS", "V1_1_1", "Strong"),
            ServiceEndpoint("TicketService", "https://easy-login.vdg-portal.de/VDGAuthPortal/services/TicketService", "V1_1_1"),
        ]
    ),
    "ergo": SmartAdminCompany(
        name="Ergo",
        easylogin_vuid="ergo",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://msv.bcs.ergo.com/imaki-bipro-sts/securitytokenservice/2.6.0.1.0", "V2_6_0", "Ticket"),
            ServiceEndpoint("TransferService", "https://services.ergo.com/transfer-service/2.6.0.1.0", "V2_6_0"),
        ]
    ),
    "finet": SmartAdminCompany(
        name="FiNet",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://webservice.finet.de/bipro/UserPasswordLogin_2.6.0.1.0", "V2_6_0", "Weak"),
            ServiceEndpoint("ExtranetService", "https://webservice.finet.de/bipro/ExtranetNavigationservice_1.0.1.0", "V1_0_1"),
        ]
    ),
    "generali": SmartAdminCompany(
        name="Generali",
        services=[
            ServiceEndpoint("SecurityTokenService", "http://www.tgic.de/generali/prod/TransferService/2.5.0.1.0", "V2_5_0", "TGICCertificate"),
            ServiceEndpoint("SecurityTokenService", "http://www.tgic.de/generali/prod/TransferService/2.5.0.1.0", "V2_5_0", "TGICmTAN"),
            ServiceEndpoint("TransferService", "https://tgic.generali.de/gev/BiproTransferService_2.5.0.1.0", "V2_5_0"),
            ServiceEndpoint("ExtranetService", "https://tgic.generali.de/gev/BiproExtranetService_1.0.1.0", "V1_0_1"),
        ]
    ),
    "gothaer": SmartAdminCompany(
        name="Gothaer",
        easylogin_vuid="Gothaer",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://basicauthsecure.gothaer.de/n410/v1-0/services/VDGTicketLogin", "V1_1_1", "Ticket"),
            ServiceEndpoint("SecurityTokenService", "https://basicauthsecure.gothaer.de/n410/v1-0/services/UserPasswordLogin", "V1_1_1", "Weak"),
            ServiceEndpoint("TransferService", "https://ssosecure.makler.gothaer.de/app/BiproGeschaeftsvorfallService/TransferService_2.6.0.1.0", "V2_6_0"),
            ServiceEndpoint("ExtranetService", "https://ssosecure.makler.gothaer.de/app/BiproExtranetService/ExtranetService", "V1_4_1"),
        ]
    ),
    "haftpflichtkasse": SmartAdminCompany(
        name="Haftpflichtkasse Darmstadt",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://suh.haftpflichtkasse.de/BiPRO/STS_X509_2.1.1.1.1", "V2_1_1", "Certificate"),
            ServiceEndpoint("TransferService", "https://suh.haftpflichtkasse.de/BiPRO/Transferservice_2.1.1.1.0", "V2_1_1"),
            ServiceEndpoint("ExtranetService", "https://suh.haftpflichtkasse.de/BiPRO/ExtranetNavigationservice_1.0.1.0", "V1_0_1"),
        ]
    ),
    "hansemerkur": SmartAdminCompany(
        name="HanseMerkur",
        services=[
            ServiceEndpoint("SecurityTokenService", "http://www.tgic.de/HanseMerkurHamburg/prod/transferservice/1.0", "V2_6_0", "TGICmTAN"),
            ServiceEndpoint("SecurityTokenService", "http://www.tgic.de/HanseMerkurHamburg/prod/transferservice/1.0", "V2_6_0", "TGICCertificate"),
            ServiceEndpoint("TransferService", "https://webservice.hansemerkur.de/bipro/services/transferservice_2.6.0.1.0", "V2_6_0"),
        ]
    ),
    "hdi": SmartAdminCompany(
        name="HDI",
        easylogin_vuid="AHG",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://easy.hdi-gerling.de/bipro-sts/services/SecurityTokenService_1.1.0.5.0", "V1_1_1", "Ticket"),
            ServiceEndpoint("SecurityTokenService", "https://easy.hdi-gerling.de/bipro-sts/services/SecurityTokenService_1.1.0.1.0", "V1_1_1", "Certificate"),
            ServiceEndpoint("TransferService", "https://easy.hdi-gerling.de/biprosfs/service/TransferService", "V1_1_1"),
            ServiceEndpoint("ExtranetService", "https://vertriebsservice.hdi.de/bipro440/ExtranetService_1.0.1.0", "V1_0_1", vuid="1033"),
        ]
    ),
    "helvetia": SmartAdminCompany(
        name="Helvetia",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://api.helvetia.com/de/helbssts/STS/UserPassword", "V2_5_0", "Weak"),
            ServiceEndpoint("SecurityTokenService", "https://api.helvetia.com/de/helbssts/STS/Cert", "V2_5_0", "Certificate"),
            ServiceEndpoint("TransferService", "https://api.helvetia.com/de/helbssts/services/Transfer/TransferService_2.6.0.1.0", "V2_6_0"),
        ]
    ),
    "ideal": SmartAdminCompany(
        name="Ideal",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://www.ideal-versicherung.de/webservice2/produktion/bipro/UsernamePasswordLogin_2.1.0.1.0", "V2_1_0", "Weak"),
            ServiceEndpoint("TransferService", "https://www.ideal-versicherung.de/webservice/produktion/bipro/transferservice_2.1.4.1.0", "V2_1_4"),
            ServiceEndpoint("ExtranetService", "https://www.ideal-versicherung.de/webservice2/produktion/bipro/extranetservice_1.4.1.0", "V1_4_1"),
        ]
    ),
    "inter": SmartAdminCompany(
        name="Inter Krankenversicherung",
        easylogin_vuid="inter",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://www.inter-makler.net/bipro/services/VDGTicketLogin", "V2_1_1", "Ticket"),
            ServiceEndpoint("TransferService", "https://inter-makler.net/axis2/services/TransferService_2.1.1.1.0", "V2_1_1"),
        ]
    ),
    "interlloyd": SmartAdminCompany(
        name="Interlloyd",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://webservice.arag.de:443/wssg/services/SecurityTokenService_2.1.3.1.0.X509TAuthentication", "V2_1_3", "Certificate"),
            ServiceEndpoint("TransferService", "https://webservice.arag.de:443/wssg/services/ILLTransferService_2.4.0.1.0", "V2_4_0"),
        ]
    ),
    "invers": SmartAdminCompany(
        name="INVERS",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://inex.inveda.net/services/BiPro_SecurityTokenService_2_6_0_1_0/", "V2_6_0", "Weak"),
            ServiceEndpoint("TransferService", "https://inex.inveda.net/services/BiPro_TransferService_2_6_0_1_0/", "V2_6_0"),
        ]
    ),
    "ists": SmartAdminCompany(
        name="ISTS",
        services=[
            ServiceEndpoint("ISTSService", "https://ists-v2.tgic.de", "V2_0_5"),
        ]
    ),
    "itzehoer": SmartAdminCompany(
        name="Itzehoer",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://bipro.itzehoer.de/bipro-sts-ws/SecurityTokenService_2.7.0.1.0", "V2_7_0", "Weak"),
            ServiceEndpoint("TransferService", "https://bipro.itzehoer.de/bipro-transfer-ws/TransferService_2.7.1.1.0", "V2_7_1"),
            ServiceEndpoint("ExtranetService", "https://bipro.itzehoer.de/exnav/services/ExtranetService-1.0.1.0", "V1_0_1"),
        ]
    ),
    "konzept_marketing": SmartAdminCompany(
        name="Konzept und Marketing",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://secure.konzept-marketing.de/bipro/410_STS/UserPasswordLogin_2.6.1.1.0", "V2_6_1", "Weak"),
            ServiceEndpoint("TransferService", "https://secure.konzept-marketing.de/bipro/430_Transfer/Service_2.6.1.1.0", "V2_6_1"),
        ]
    ),
    "kravag": SmartAdminCompany(
        name="KRAVAG",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://webservice.ruv.de/bipro/sts/2.4.0.1.0", "V2_4_0", "Weak"),
            ServiceEndpoint("TransferService", "https://webservice.ruv.de/bipro/TransferService/2.4.4.1.1", "V2_4_4_1_1"),
            ServiceEndpoint("ExtranetService", "https://webservice.ruv.de/bipro/ExtranetService/1.0.1.0", "V1_0_1", vuid="5058"),
        ]
    ),
    "ks_auxilia": SmartAdminCompany(
        name="KS AUXILIA",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://portal.ks-auxilia.de/bipro/authenticate", "V1_1_1", "Weak"),
            ServiceEndpoint("TransferService", "https://portal.ks-auxilia.de/bipro/transfer", "V1_1_1"),
            ServiceEndpoint("ExtranetService", "https://portal.ks-auxilia.de/bipro/extranet", "V1_4_1"),
        ]
    ),
    "lv1871": SmartAdminCompany(
        name="LV1871",
        easylogin_vuid="lv1871-test",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://sts.lv1871.de/sts_v2/services/VDGTicketLogin_2.1.1.1.1", "V2_1_1", "Ticket"),
            ServiceEndpoint("SecurityTokenService", "https://sts.lv1871.de/sts_v2/validationservice_v2_0/SCTValidation_2.1.1.1.1", "V2_1_1", "Certificate"),
            ServiceEndpoint("TransferService", "https://informer.lv1871.de/bipro/services/TransferService_2.1.1.1.0", "V2_1_1"),
            ServiceEndpoint("ExtranetService", "https://informer.lv1871.de/bipro/services/ExtranetService_1.4.1.0", "V1_4_1", vuid="1062"),
        ]
    ),
    "neodigital": SmartAdminCompany(
        name="Neodigital",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://myneo.neodigital.de/NDBiproSecurityTokenService/services/SecurityTokenService_2.6.0.1.0", "V2_6_0", "Weak"),
            ServiceEndpoint("TransferService", "https://myneo.neodigital.de/NDBiproTransferGevoWebService/services/TransferService_2.6.0.1.0", "V2_6_0"),
            ServiceEndpoint("ExtranetService", "https://myneo.neodigital.de/NDBiproExtranetWebService/services/ExtranetService_1.7.1.0", "V1_4_1"),
        ]
    ),
    "nuernberger": SmartAdminCompany(
        name="Nürnberger",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://web.services.nuernberger.de/sts", "V2_5_0", "Certificate"),
            ServiceEndpoint("TransferService", "https://web.services.nuernberger.de/TransferService_2.6.1.0.0", "V2_6_1"),
            ServiceEndpoint("ExtranetService", "https://web.services.nuernberger.de/ExtranetService_1.7.1.0", "V1_4_1"),
        ]
    ),
    "ostangler": SmartAdminCompany(
        name="Ostangler Brandgilde",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://www.ostangler-portal.de/BiPro430/services/SecurityTokenService_2.4.0.1.0", "V2_4_0", "Weak"),
            ServiceEndpoint("TransferService", "https://www.ostangler-portal.de/BiPro430/services/TransferService_2.4.0.1.0", "V2_4_0"),
            ServiceEndpoint("ExtranetService", "https://www.ostangler-portal.de/BiPro440/services/ExtranetService_1.0.1.0", "V1_0_1"),
        ]
    ),
    "rheinland": SmartAdminCompany(
        name="Rheinland",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://services.rhion.de/rhld/sts/external/ws/SecurityTokenService_2.1.6.1.0", "V2_1_4", "Weak"),
            ServiceEndpoint("SecurityTokenService", "https://services.rhion.de/rhld/sts/external/ws/SecurityTokenService_2.1.6.1.0", "V2_1_4", "Certificate"),
            ServiceEndpoint("TransferService", "https://services.rhion.de/bipro430-service/services/TransferService_2.6.0.1.0", "V2_6_0"),
            ServiceEndpoint("ExtranetService", "https://services.rhion.de/ws/extranet/bipro440/V1.4.1.0/ExtranetService_1.4.1.0", "V1_4_1", vuid="5798"),
        ]
    ),
    "rhion": SmartAdminCompany(
        name="Rhion",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://services.rhion.de/rhld/sts/external/ws/SecurityTokenService_2.1.6.1.0", "V2_1_4", "Weak"),
            ServiceEndpoint("SecurityTokenService", "https://services.rhion.de/rhld/sts/external/ws/SecurityTokenService_2.1.6.1.0", "V2_1_4", "Certificate"),
            ServiceEndpoint("TransferService", "https://services.rhion.de/bipro430-service/services/TransferService_2.6.0.1.0", "V2_6_0"),
            ServiceEndpoint("ExtranetService", "https://services.rhion.de/ws/extranet/bipro440/V1.4.1.0/ExtranetService_1.4.1.0", "V1_4_1", vuid="5121"),
        ]
    ),
    "rv": SmartAdminCompany(
        name="R+V",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://webservice.ruv.de/bipro/sts/2.4.0.1.0", "V2_4_0", "Weak"),
            ServiceEndpoint("TransferService", "https://webservice.ruv.de/bipro/TransferService/2.6.2.1.0", "V2_6_2"),
            ServiceEndpoint("ExtranetService", "https://webservice.ruv.de/bipro/ExtranetService/1.0.1.0", "V1_0_1", vuid="5438"),
        ]
    ),
    "stuttgarter": SmartAdminCompany(
        name="Stuttgarter",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://bipro-ws.stuttgarter.de/sts/services/sts_webservice_2.1.0.1.2.STSUNPService_2.1.0.1.2", "V2_1_1", "Weak"),
            ServiceEndpoint("SecurityTokenService", "https://bipro-ws.stuttgarter.de/sts/services/sts_webservice_2.1.0.1.2.STSCertService_2.1.0.1.2", "V2_1_1", "Certificate"),
            ServiceEndpoint("TransferService", "https://bipro-ws.stuttgarter.de/pks/3.0/TransferService_2.6.1.1.0", "V2_6_1"),
            ServiceEndpoint("ExtranetService", "https://bipro-ws.stuttgarter.de/deeplink/1.0/DeeplinkService_1.4.3.0", "V1_4_1"),
        ]
    ),
    "swiss_life": SmartAdminCompany(
        name="Swiss Life",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://www.swisslife-weboffice.de/BiPRO/410_STS/UserPasswordLogin_2.5.0.1.0", "V2_5_0", "Weak"),
            ServiceEndpoint("TransferService", "https://www.swisslife-weboffice.de/BiPRO/430_Transfer/Service_2.5.0.1.0", "V2_5_0"),
            ServiceEndpoint("ExtranetService", "https://www.swisslife-weboffice.de/BiPRO/440_Extranet/Service_1.0.1.0", "V1_0_1", vuid="1090"),
        ]
    ),
    "vema": SmartAdminCompany(
        name="VEMA",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://bipro.vemaeg.de/va/UserPasswordLogin_2.6.1.1.0", "V2_6_1", "Weak"),
            ServiceEndpoint("TransferService", "https://bipro.vemaeg.de/va/TransferService_2.6.1.1.0", "V2_6_1"),
            ServiceEndpoint("ExtranetService", "https://bipro.vemaeg.de/va/ExtranetService_1.0.1.0", "V1_0_1"),
        ]
    ),
    "vhv": SmartAdminCompany(
        name="VHV",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://sts.vhv.de/sts/services/SecurityTokenServiceUsernamePWOTP_1.0.1.0", "V1_1_1", "Strong"),
            ServiceEndpoint("TransferService", "https://vermittlerws.vhv.de/VermittlerWS/services/TransferService_2.1.1.1.0", "V2_1_1"),
            ServiceEndpoint("ExtranetService", "https://maxnet.vhv.de/Bipro440WS/services/ExtranetService_1.0.1.0", "V1_0_1", vuid="5862"),
        ]
    ),
    "volkswohlbund": SmartAdminCompany(
        name="Volkswohlbund",
        easylogin_vuid="vb",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://vbnet.volkswohl-bund.de/BiPROAuth/services/VDGTicketLogin", "V1_1_1", "Ticket"),
            ServiceEndpoint("TransferService", "https://vbnet3.volkswohl-bund.de/vorgangsdaten/services/soap/transfer_1.1.1.0", "V1_1_1"),
            ServiceEndpoint("ExtranetService", "https://vbnet.volkswohl-bund.de/BiPROExtranet/services/ExtranetService", "V1_4_1"),
        ]
    ),
    "wwk": SmartAdminCompany(
        name="WWK",
        easylogin_vuid="wwk",
        services=[
            ServiceEndpoint("SecurityTokenService", "https://bipro.wwk.de/ibis/services/VDGTicketLogin_2.4.0.1.0", "V2_4_0", "Ticket"),
            ServiceEndpoint("SecurityTokenService", "https://bipro.wwk.de/ibis/services/UsernamePasswordLogin_2.4.0.1.0", "V2_4_0", "Weak"),
            ServiceEndpoint("TransferService", "https://bipro.wwk.de/ibis/services/transferservice_2.4.0.1.0", "V2_4_0"),
            ServiceEndpoint("ExtranetService", "https://bipro.wwk.de/ibis/services/extranetservice_1.0.1.0", "V1_0_1"),
        ]
    ),
}


# =============================================================================
# HILFSFUNKTIONEN
# =============================================================================

def get_company_by_name(name: str) -> Optional[SmartAdminCompany]:
    """Sucht einen Versicherer nach Namen (case-insensitive)."""
    name_lower = name.lower().replace(" ", "_").replace("-", "_")
    
    # Direkte Suche
    if name_lower in SMARTADMIN_COMPANIES:
        return SMARTADMIN_COMPANIES[name_lower]
    
    # Fuzzy-Suche
    for key, company in SMARTADMIN_COMPANIES.items():
        if name_lower in company.name.lower() or company.name.lower() in name_lower:
            return company
    
    return None


def get_all_companies() -> List[SmartAdminCompany]:
    """Gibt alle Versicherer zurück."""
    return list(SMARTADMIN_COMPANIES.values())


def get_companies_by_auth_type(auth_type: str) -> List[SmartAdminCompany]:
    """Gibt alle Versicherer mit einem bestimmten Auth-Typ zurück."""
    result = []
    for company in SMARTADMIN_COMPANIES.values():
        if auth_type in company.get_auth_types():
            result.append(company)
    return result


def get_easylogin_companies() -> List[SmartAdminCompany]:
    """Gibt alle Versicherer mit EasyLogin-Unterstützung zurück."""
    return [c for c in SMARTADMIN_COMPANIES.values() if c.easylogin_vuid]
