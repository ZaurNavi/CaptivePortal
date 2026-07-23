"""
Omada Controller Provider.

Implementation of the ControllerInterface for TP-Link Omada SDN Controller.
Real OpenAPI implementation (v1.5).
"""

import requests
from typing import List, Dict, Any

from app.controllers.base import ControllerInterface
from app.logger import logger
from app.models import Result
from app import get_settings


class OmadaProvider(ControllerInterface):
    """Omada SDN Controller Provider."""

    def __init__(self):
        """Initialize the Omada provider with settings."""
        logger.debug("Initializing OmadaProvider")
        settings = get_settings()
        self._omada_url = settings["omada_url"].rstrip("/")
        self._omada_id = settings["omada_id"]
        self._client_id = settings["client_id"]
        self._client_secret = settings["client_secret"]
        self._verify_ssl = settings["verify_ssl"]

    def _get_token(self) -> Result:
        """Internal method to get Access Token. Returns Result with token in data."""
        url = f"{self._omada_url}/openapi/authorize/token?grant_type=client_credentials"
        payload = {
            "omadacId": self._omada_id,
            "client_id": self._client_id,
            "client_secret": self._client_secret
        }
        
        logger.info("Getting access token")
        try:
            response = requests.post(url, json=payload, verify=self._verify_ssl)
            logger.debug(f"Token request HTTP status: {response.status_code}")
            logger.debug(f"Token response: {response.text}")
            
            data = response.json()
            if data.get("errorCode") == 0:
                token = data["result"]["accessToken"]
                logger.debug("Access Token received successfully")
                return Result.ok(message=data.get("msg", "Success"), data={"token": token})
            else:
                logger.warning("Token request failed")
                return Result.fail(error="TOKEN_FAILED", message=data.get("msg", "Unknown token error"))
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Error during token request: {str(e)}")
            return Result.fail(error="HTTP_ERROR", message=f"HTTP Error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during token request: {str(e)}")
            return Result.fail(error="UNEXPECTED_ERROR", message=f"Unexpected error: {str(e)}")

    def connect(self) -> None:
        """Establish connection to the Omada controller."""
        logger.info("Connecting to Omada controller...")
        logger.info("Omada provider ready (dynamic token per request)")

    def get_sites(self) -> List[Dict[str, Any]]:
        """Retrieve list of sites from the Omada controller."""
        logger.info("Fetching sites from Omada controller")
        
        token_result = self._get_token()
        if not token_result.success:
            logger.error("Failed to get token for get_sites")
            return []
        
        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites?page=1&pageSize=100"
        headers = {"Authorization": f"AccessToken={token}"}
        
        try:
            response = requests.get(url, headers=headers, verify=self._verify_ssl)
            logger.debug(f"Sites request HTTP status: {response.status_code}")
            logger.debug(f"Sites response: {response.text}")
            
            data = response.json()
            if data.get("errorCode") == 0:
                sites_data = data.get("result", {}).get("data", [])
                logger.info(f"Successfully fetched {len(sites_data)} sites")
                return sites_data
            else:
                logger.error(f"Failed to get sites: {data.get('msg')}")
                return []
        except Exception as e:
            logger.error(f"Error during get_sites: {str(e)}")
            return []

    def get_clients(self, site_id: str) -> List[Dict[str, Any]]:
        """Retrieve list of clients for a specific site."""
        logger.debug(f"Fetching clients for site {site_id} (stub)")
        return []

    def authorize(self, site_id: str, client_mac: str) -> Result:
        """Authorize a client on the specified site."""
        logger.info(f"Authorizing client {client_mac} on site {site_id}")
        
        token_result = self._get_token()
        if not token_result.success:
            return token_result
        
        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites/{site_id}/hotspot/clients/{client_mac}/auth"
        headers = {"Authorization": f"AccessToken={token}"}
        
        logger.debug(f"Calling endpoint: POST {url}")
        try:
            response = requests.post(url, headers=headers, verify=self._verify_ssl)
            logger.debug(f"Auth request HTTP status: {response.status_code}")
            logger.debug(f"Auth response: {response.text}")
            
            data = response.json()
            if data.get("errorCode") == 0:
                return Result.ok(message=data.get("msg", "Success"))
            else:
                return Result.fail(error="AUTH_FAILED", message=data.get("msg", "Unknown authorization error"))
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Error during authorization: {str(e)}")
            return Result.fail(error="HTTP_ERROR", message=f"HTTP Error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during authorization: {str(e)}")
            return Result.fail(error="UNEXPECTED_ERROR", message=f"Unexpected error: {str(e)}")

    def unauthorize(self, site_id: str, client_mac: str) -> Result:
        """Unauthorize (revoke) a client on the specified site."""
        logger.info(f"Unauthorized client {client_mac} on site {site_id}")
        
        token_result = self._get_token()
        if not token_result.success:
            return token_result
        
        token = token_result.data.get("token")
        url = f"{self._omada_url}/openapi/v1/{self._omada_id}/sites/{site_id}/hotspot/clients/{client_mac}/auth"
        headers = {"Authorization": f"AccessToken={token}"}
        
        logger.debug(f"Calling endpoint: DELETE {url}")
        try:
            response = requests.delete(url, headers=headers, verify=self._verify_ssl)
            logger.debug(f"Unauth request HTTP status: {response.status_code}")
            logger.debug(f"Unauth response: {response.text}")
            
            data = response.json()
            if data.get("errorCode") == 0:
                return Result.ok(message=data.get("msg", "Success"))
            else:
                return Result.fail(error="UNAUTH_FAILED", message=data.get("msg", "Unknown unauthorization error"))
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP Error during unauthorization: {str(e)}")
            return Result.fail(error="HTTP_ERROR", message=f"HTTP Error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during unauthorization: {str(e)}")
            return Result.fail(error="UNEXPECTED_ERROR", message=f"Unexpected error: {str(e)}")
