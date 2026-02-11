"""OFAC SDN XML parser."""

import hashlib
import logging
import re
from datetime import date
from typing import Optional
from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OFACCitation(BaseModel):
    """Citation for OFAC SDN data."""

    ofac_uid: str = Field(..., description="OFAC unique identifier")
    source_url: str = Field(
        default="https://www.treasury.gov/ofac/downloads/sdn.xml",
        description="Source URL for SDN list",
    )
    source_name: str = Field(
        default="OFAC SDN List",
        description="Human-readable source name",
    )
    publish_date: Optional[date] = Field(None, description="List publish date")
    raw_text: str = Field(..., description="Raw XML snippet or entry text")
    raw_text_hash: str = Field(..., description="SHA-256 hash of raw text")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (1.0 for government source)",
    )

    @classmethod
    def create(
        cls,
        ofac_uid: str,
        raw_text: str,
        publish_date: Optional[date] = None,
    ) -> "OFACCitation":
        """Create citation with computed hash."""
        return cls(
            ofac_uid=ofac_uid,
            publish_date=publish_date,
            raw_text=raw_text[:2000],  # Limit size
            raw_text_hash=hashlib.sha256(raw_text.encode()).hexdigest()[:16],
        )


class SDNEntry(BaseModel):
    """Parsed SDN entry."""

    uid: str = Field(..., description="OFAC unique identifier")
    name: str = Field(..., description="Primary name")
    entity_type: str = Field(..., description="'individual' or 'entity'")
    programs: list[str] = Field(
        default_factory=list,
        description="Sanctions programs (SDGT, IRAN, etc.)",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names/aliases",
    )
    addresses: list[str] = Field(
        default_factory=list,
        description="Known addresses",
    )
    nationality: Optional[str] = Field(None, description="Nationality if known")
    date_of_birth: Optional[str] = Field(None, description="Date of birth if known")
    id_numbers: list[str] = Field(
        default_factory=list,
        description="ID numbers (passport, tax ID, etc.)",
    )
    remarks: Optional[str] = Field(None, description="Additional remarks")
    citation: OFACCitation = Field(..., description="Source citation")


class OFACParser:
    """Parser for OFAC SDN XML format."""

    # OFAC XML namespaces (handle both old and new)
    NAMESPACES = {
        "sdn": "http://www.un.org/sanctions/1.0",
        "": "",  # No namespace fallback
    }

    def __init__(self):
        self.publish_date: Optional[date] = None
        self.entry_count = 0

    def parse(self, xml_content: str, source_date: Optional[date] = None) -> list[SDNEntry]:
        """
        Parse SDN XML content into structured entries.

        Args:
            xml_content: Raw XML string
            source_date: Date when the list was downloaded

        Returns:
            List of parsed SDNEntry objects
        """
        self.publish_date = source_date
        entries = []

        try:
            # Parse XML
            root = ET.fromstring(xml_content)

            # Try to extract publish date from XML
            self._extract_publish_date(root)

            # Find all sdnEntry elements (try with and without namespace)
            sdn_entries = self._find_entries(root)

            logger.info(f"Found {len(sdn_entries)} SDN entries")

            for entry_elem in sdn_entries:
                try:
                    entry = self._parse_entry(entry_elem)
                    if entry:
                        entries.append(entry)
                        self.entry_count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse entry: {e}")
                    continue

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            raise ValueError(f"Invalid XML content: {e}")

        logger.info(f"Successfully parsed {len(entries)} SDN entries")
        return entries

    def _find_entries(self, root: ET.Element) -> list[ET.Element]:
        """Find all sdnEntry elements, handling namespace variations."""
        # Try with namespace
        entries = root.findall(".//sdn:sdnEntry", self.NAMESPACES)
        if entries:
            return entries

        # Try without namespace
        entries = root.findall(".//sdnEntry")
        if entries:
            return entries

        # Try finding by tag suffix
        for elem in root.iter():
            if elem.tag.endswith("sdnEntry"):
                # Found the namespace, extract it
                ns = elem.tag.split("}")[0] + "}" if "}" in elem.tag else ""
                return root.findall(f".//{ns}sdnEntry")

        return []

    def _extract_publish_date(self, root: ET.Element) -> None:
        """Try to extract publish date from XML."""
        # Look for publshInformation or dateOfIssue
        for tag in ["publshInformation", "dateOfIssue", "Publish_Date"]:
            elem = self._find_element(root, tag)
            if elem is not None and elem.text:
                try:
                    # Try common date formats
                    for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                        try:
                            self.publish_date = date.fromisoformat(elem.text.strip())
                            return
                        except ValueError:
                            continue
                except Exception:
                    pass

    def _find_element(
        self,
        parent: ET.Element,
        tag: str,
    ) -> Optional[ET.Element]:
        """Find element by tag, handling namespace variations."""
        # Try with namespace
        for ns_prefix in self.NAMESPACES:
            if ns_prefix:
                elem = parent.find(f"{ns_prefix}:{tag}", self.NAMESPACES)
            else:
                elem = parent.find(tag)
            if elem is not None:
                return elem

        # Try by tag suffix
        for child in parent:
            if child.tag.endswith(tag):
                return child

        return None

    def _find_all_elements(
        self,
        parent: ET.Element,
        tag: str,
    ) -> list[ET.Element]:
        """Find all elements by tag, handling namespace variations."""
        results = []

        # Try with namespace
        for ns_prefix in self.NAMESPACES:
            if ns_prefix:
                results.extend(parent.findall(f".//{ns_prefix}:{tag}", self.NAMESPACES))
            else:
                results.extend(parent.findall(f".//{tag}"))

        if results:
            return results

        # Try by tag suffix
        for elem in parent.iter():
            if elem.tag.endswith(tag):
                results.append(elem)

        return results

    def _get_text(self, parent: ET.Element, tag: str) -> Optional[str]:
        """Get text content of a child element."""
        elem = self._find_element(parent, tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return None

    def _parse_entry(self, entry_elem: ET.Element) -> Optional[SDNEntry]:
        """Parse a single sdnEntry element."""
        # Get UID
        uid = self._get_text(entry_elem, "uid")
        if not uid:
            return None

        # Get name parts
        first_name = self._get_text(entry_elem, "firstName") or ""
        last_name = self._get_text(entry_elem, "lastName") or ""

        # Construct full name
        if first_name and last_name:
            name = f"{first_name} {last_name}"
        elif last_name:
            name = last_name
        elif first_name:
            name = first_name
        else:
            return None

        # Get entity type
        sdn_type = self._get_text(entry_elem, "sdnType") or "Individual"
        entity_type = "individual" if sdn_type.lower() == "individual" else "entity"

        # Get programs
        programs = []
        program_list = self._find_element(entry_elem, "programList")
        if program_list is not None:
            for prog in self._find_all_elements(program_list, "program"):
                if prog.text:
                    programs.append(prog.text.strip())

        # Get aliases
        aliases = []
        aka_list = self._find_element(entry_elem, "akaList")
        if aka_list is not None:
            for aka in self._find_all_elements(aka_list, "aka"):
                aka_first = self._get_text(aka, "firstName") or ""
                aka_last = self._get_text(aka, "lastName") or ""
                aka_name = f"{aka_first} {aka_last}".strip()
                if aka_name and aka_name != name:
                    aliases.append(aka_name)

        # Get addresses
        addresses = []
        addr_list = self._find_element(entry_elem, "addressList")
        if addr_list is not None:
            for addr in self._find_all_elements(addr_list, "address"):
                addr_parts = []
                for field in ["address1", "address2", "address3", "city", "stateOrProvince", "postalCode", "country"]:
                    val = self._get_text(addr, field)
                    if val:
                        addr_parts.append(val)
                if addr_parts:
                    addresses.append(", ".join(addr_parts))

        # Get nationality
        nationality = None
        nat_list = self._find_element(entry_elem, "nationalityList")
        if nat_list is not None:
            nat = self._find_element(nat_list, "nationality")
            if nat is not None:
                nationality = self._get_text(nat, "country")

        # Get date of birth
        dob = None
        dob_list = self._find_element(entry_elem, "dateOfBirthList")
        if dob_list is not None:
            dob_item = self._find_element(dob_list, "dateOfBirthItem")
            if dob_item is not None:
                dob = self._get_text(dob_item, "dateOfBirth")

        # Get ID numbers
        id_numbers = []
        id_list = self._find_element(entry_elem, "idList")
        if id_list is not None:
            for id_item in self._find_all_elements(id_list, "id"):
                id_type = self._get_text(id_item, "idType") or "ID"
                id_num = self._get_text(id_item, "idNumber")
                id_country = self._get_text(id_item, "idCountry")
                if id_num:
                    id_str = f"{id_type}: {id_num}"
                    if id_country:
                        id_str += f" ({id_country})"
                    id_numbers.append(id_str)

        # Get remarks
        remarks = self._get_text(entry_elem, "remarks")

        # Build raw text for citation
        raw_text = self._build_raw_text(
            uid=uid,
            name=name,
            entity_type=entity_type,
            programs=programs,
            aliases=aliases,
        )

        # Create citation
        citation = OFACCitation.create(
            ofac_uid=uid,
            raw_text=raw_text,
            publish_date=self.publish_date,
        )

        return SDNEntry(
            uid=uid,
            name=name,
            entity_type=entity_type,
            programs=programs,
            aliases=aliases,
            addresses=addresses,
            nationality=nationality,
            date_of_birth=dob,
            id_numbers=id_numbers,
            remarks=remarks,
            citation=citation,
        )

    def _build_raw_text(
        self,
        uid: str,
        name: str,
        entity_type: str,
        programs: list[str],
        aliases: list[str],
    ) -> str:
        """Build raw text representation for citation."""
        parts = [
            f"OFAC UID: {uid}",
            f"Name: {name}",
            f"Type: {entity_type}",
        ]
        if programs:
            parts.append(f"Programs: {', '.join(programs)}")
        if aliases:
            parts.append(f"Aliases: {', '.join(aliases[:5])}")  # Limit aliases
        return " | ".join(parts)

    def get_stats(self) -> dict:
        """Get parsing statistics."""
        return {
            "entries_parsed": self.entry_count,
            "publish_date": str(self.publish_date) if self.publish_date else None,
        }
