"""Template management system for trade plan YAML files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Any
import yaml

from loguru import logger

from .trade_plan import TradePlan
from .validation_engine import ValidationEngine


class TemplateManager:
    """Manages YAML template files for trade plans."""
    
    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        """
        Initialize template manager.
        
        Args:
            templates_dir: Directory containing template files. 
                         Defaults to data/trade_plans/templates/
        """
        if templates_dir is None:
            # Default to project template directory
            project_root = Path(__file__).parents[3]  # Go up from src/auto_trader/models/
            templates_dir = project_root / "data" / "trade_plans" / "templates"
        
        self.templates_dir = Path(templates_dir)
        self._validation_engine = ValidationEngine()
    
    def list_available_templates(self) -> Dict[str, Path]:
        """
        List all available template files.
        
        Returns:
            Dictionary mapping template names to file paths
        """
        templates = {}
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return templates
        
        for template_file in self.templates_dir.glob("*.yaml"):
            template_name = template_file.stem
            templates[template_name] = template_file
        
        for template_file in self.templates_dir.glob("*.yml"):
            template_name = template_file.stem
            templates[template_name] = template_file
        
        logger.info(f"Found {len(templates)} templates", templates=list(templates.keys()))
        return templates
    
    def load_template(self, template_name: str) -> str:
        """
        Load template content by name.
        
        Args:
            template_name: Name of template to load (without extension)
            
        Returns:
            Template content as string
            
        Raises:
            FileNotFoundError: If template doesn't exist
            PermissionError: If template can't be read
        """
        templates = self.list_available_templates()
        
        if template_name not in templates:
            available = ", ".join(templates.keys())
            raise FileNotFoundError(
                f"Template '{template_name}' not found. "
                f"Available templates: {available}"
            )
        
        template_path = templates[template_name]
        
        try:
            content = template_path.read_text(encoding='utf-8')
            logger.info(f"Loaded template '{template_name}'", path=str(template_path))
            return content
        except Exception as e:
            logger.error(f"Failed to load template '{template_name}'", error=str(e))
            raise
    
    def get_template_documentation(self, template_name: str) -> Dict[str, Any]:
        """
        Extract documentation from template comments.
        
        Args:
            template_name: Name of template to analyze
            
        Returns:
            Dictionary with template documentation
        """
        try:
            content = self.load_template(template_name)
        except FileNotFoundError:
            return {"error": f"Template '{template_name}' not found"}
        
        lines = content.split('\n')
        doc_info = {
            "name": template_name,
            "description": "",
            "required_fields": [],
            "optional_fields": [],
            "parameters": {},
            "examples": [],
            "use_cases": [],
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Extract main description from first comment
            if line.startswith('#') and not doc_info["description"]:
                desc = line.lstrip('# ').strip()
                if desc and not desc.startswith("This template"):
                    doc_info["description"] = desc
                elif desc.startswith("This template"):
                    doc_info["description"] = desc
            
            # Extract field documentation
            if line.startswith('#') and "(REQUIRED)" in line:
                field_match = re.search(r'(\w+).*\(REQUIRED\)', line)
                if field_match:
                    doc_info["required_fields"].append(field_match.group(1))
            
            if line.startswith('#') and "(OPTIONAL)" in line:
                field_match = re.search(r'(\w+).*\(OPTIONAL\)', line)
                if field_match:
                    doc_info["optional_fields"].append(field_match.group(1))
            
            # Extract examples
            if (line.startswith('# Example') and ':' in line) or line.startswith('# plan_id:'):
                if ':' in line:
                    example = line.split(':', 1)[1].strip()
                    if example and example != '':
                        doc_info["examples"].append(example)
                elif line.startswith('# plan_id:') or line.startswith('# symbol:'):
                    # Extract inline examples
                    example = line.lstrip('# ').strip()
                    if example:
                        doc_info["examples"].append(example)
            
            # Extract use cases
            if "# Common Use Cases:" in line or "# Use Cases:" in line:
                current_section = "use_cases"
            elif current_section == "use_cases" and line.startswith('# '):
                use_case = line.lstrip('# ').strip()
                if use_case and use_case.startswith(('1.', '2.', '3.', '-')):
                    doc_info["use_cases"].append(use_case)
        
        return doc_info
    
    def customize_template(
        self,
        template_name: str,
        substitutions: Dict[str, Any],
        validate: bool = True
    ) -> str:
        """
        Customize template with user-provided values.
        
        Args:
            template_name: Name of template to customize
            substitutions: Dictionary of values to substitute
            validate: Whether to validate the resulting YAML
            
        Returns:
            Customized template content
            
        Raises:
            ValueError: If validation fails or substitutions are invalid
        """
        content = self.load_template(template_name)
        
        # Perform substitutions
        customized_content = self._apply_substitutions(content, substitutions)
        
        # Validate if requested
        if validate:
            result = self._validation_engine.validate_yaml_content(customized_content)
            if not result.is_valid:
                error_summary = result.get_error_summary()
                raise ValueError(f"Template customization failed validation:\n{error_summary}")
        
        logger.info(
            f"Customized template '{template_name}'",
            substitutions=substitutions,
            validated=validate
        )
        
        return customized_content
    
    def create_plan_from_template(
        self,
        template_name: str,
        plan_data: Dict[str, Any],
        output_file: Optional[Path] = None
    ) -> TradePlan:
        """
        Create a complete trade plan from template.
        
        Args:
            template_name: Template to use as base
            plan_data: Data to populate in template
            output_file: Optional file to write customized plan
            
        Returns:
            Validated TradePlan instance
            
        Raises:
            ValueError: If plan data is invalid
        """
        # Customize template
        customized_content = self.customize_template(template_name, plan_data, validate=True)
        
        # Parse the YAML
        parsed_data = yaml.safe_load(customized_content)
        
        # Create TradePlan instance
        trade_plan = TradePlan(**parsed_data)
        
        # Save to file if requested
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(customized_content, encoding='utf-8')
            logger.info(f"Saved trade plan to {output_file}", plan_id=trade_plan.plan_id)
        
        return trade_plan
    
    def _apply_substitutions(self, content: str, substitutions: Dict[str, Any]) -> str:
        """Apply value substitutions to template content."""
        lines = content.split('\n')
        result_lines = []
        
        for line in lines:
            # Skip comment lines
            if line.strip().startswith('#'):
                result_lines.append(line)
                continue
            
            # Process YAML value lines
            processed_line = line
            for key, value in substitutions.items():
                # Handle various substitution patterns
                patterns = [
                    f'{key}: "SYMBOL_YYYYMMDD_001"',  # plan_id pattern
                    f'{key}: "SYMBOL"',               # symbol pattern
                    f'{key}: 0.00',                   # price pattern
                    f'{key}: "normal"',               # category pattern
                    'threshold: 0.00',               # parameter pattern
                ]
                
                for pattern in patterns:
                    if pattern in processed_line:
                        if isinstance(value, str):
                            replacement = f'{key}: "{value}"'
                        else:
                            replacement = f'{key}: {value}'
                        
                        processed_line = processed_line.replace(pattern, replacement)
                        break
                
                # Handle parameter substitutions
                if 'threshold:' in processed_line and key == 'threshold':
                    processed_line = re.sub(
                        r'threshold: [\d.]+',
                        f'threshold: {value}',
                        processed_line
                    )
            
            result_lines.append(processed_line)
        
        return '\n'.join(result_lines)
    
    def validate_template(self, template_name: str) -> bool:
        """
        Validate that a template has correct structure.
        
        Args:
            template_name: Name of template to validate
            
        Returns:
            True if template is valid, False otherwise
        """
        try:
            content = self.load_template(template_name)
            
            # Check for required sections
            required_patterns = [
                r'plan_id:',
                r'symbol:',
                r'entry_level:',
                r'stop_loss:',
                r'take_profit:',
                r'risk_category:',
                r'entry_function:',
                r'exit_function:',
            ]
            
            for pattern in required_patterns:
                if not re.search(pattern, content):
                    logger.warning(
                        f"Template '{template_name}' missing required field",
                        pattern=pattern
                    )
                    return False
            
            # Try to parse as YAML (with placeholder values)
            try:
                yaml.safe_load(content)
            except yaml.YAMLError as e:
                logger.warning(
                    f"Template '{template_name}' has YAML syntax issues",
                    error=str(e)
                )
                return False
            
            logger.info(f"Template '{template_name}' validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Template '{template_name}' validation failed", error=str(e))
            return False
    
    def get_template_summary(self) -> Dict[str, Any]:
        """
        Get summary of all available templates.
        
        Returns:
            Summary information about templates
        """
        templates = self.list_available_templates()
        
        summary = {
            "total_templates": len(templates),
            "templates": {},
            "validation_results": {}
        }
        
        for name, path in templates.items():
            doc_info = self.get_template_documentation(name)
            is_valid = self.validate_template(name)
            
            summary["templates"][name] = {
                "path": str(path),
                "description": doc_info.get("description", ""),
                "required_fields": len(doc_info.get("required_fields", [])),
                "optional_fields": len(doc_info.get("optional_fields", [])),
                "examples": len(doc_info.get("examples", [])),
                "use_cases": len(doc_info.get("use_cases", [])),
            }
            
            summary["validation_results"][name] = is_valid
        
        return summary