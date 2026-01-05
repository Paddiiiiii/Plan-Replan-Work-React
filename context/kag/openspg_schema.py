"""OpenSPG KAG Schema定义"""

SCHEMA_DEFINITION = """
# ============ 基础类型 ============
OperationalUnit(作战单元): EntityType
  properties:
    name(名称): Text
      index: TextAndVector
    category(类别): Text
      index: Text
    description(描述): Text
      index: TextAndVector

CapabilityProfile(能力剖面): EntityType
  properties:
    name(名称): Text
      index: TextAndVector
    effectiveRangeMin(有效范围下限): Number
      unit: 'm'
    effectiveRangeMax(有效范围上限): Number
      unit: 'm'
    maxRange(最大范围): Number
      unit: 'm'
    note(备注): Text
      index: TextAndVector

DeploymentConstraint(部署约束): EntityType
  properties:
    elevationBand(高程等级): Text
      index: Text
    slopeBand(坡度等级): Text
      index: Text
    surfaceCover(地表类型): Text
      index: Text
    bufferMin(缓冲距离下限): Number
      unit: 'm'
    bufferMax(缓冲距离上限): Number
      unit: 'm'
    rationale(说明): Text
      index: TextAndVector

PlaceFeature(环境要素): EntityType
  properties:
    name(名称): Text
      index: TextAndVector
    type(类型): Text
      index: Text
    description(描述): Text
      index: TextAndVector

# ============ 关系 ============
hasCapability(具备能力): RelationType
  source: OperationalUnit
  target: CapabilityProfile
  properties:
    confidence(置信度): Number

hasDeploymentConstraint(部署约束): RelationType
  source: OperationalUnit
  target: DeploymentConstraint
  properties:
    confidence(置信度): Number

suitableOn(适用环境): RelationType
  source: OperationalUnit
  target: PlaceFeature
  properties:
    note(备注): Text
      index: Text

constraintRefersTo(约束涉及): RelationType
  source: DeploymentConstraint
  target: PlaceFeature
  properties:
    aspect(维度): Text
      index: Text
"""

ENTITY_TYPES = {
    "OperationalUnit": {
        "description": "作战单元",
        "properties": {
            "name": {"type": "Text", "index": "TextAndVector"},
            "category": {"type": "Text", "index": "Text"},
            "description": {"type": "Text", "index": "TextAndVector"}
        }
    },
    "CapabilityProfile": {
        "description": "能力剖面",
        "properties": {
            "name": {"type": "Text", "index": "TextAndVector"},
            "effectiveRangeMin": {"type": "Number", "unit": "m"},
            "effectiveRangeMax": {"type": "Number", "unit": "m"},
            "maxRange": {"type": "Number", "unit": "m"},
            "note": {"type": "Text", "index": "TextAndVector"}
        }
    },
    "DeploymentConstraint": {
        "description": "部署约束",
        "properties": {
            "elevationBand": {"type": "Text", "index": "Text"},
            "slopeBand": {"type": "Text", "index": "Text"},
            "surfaceCover": {"type": "Text", "index": "Text"},
            "bufferMin": {"type": "Number", "unit": "m"},
            "bufferMax": {"type": "Number", "unit": "m"},
            "rationale": {"type": "Text", "index": "TextAndVector"}
        }
    },
    "PlaceFeature": {
        "description": "环境要素",
        "properties": {
            "name": {"type": "Text", "index": "TextAndVector"},
            "type": {"type": "Text", "index": "Text"},
            "description": {"type": "Text", "index": "TextAndVector"}
        }
    }
}

RELATION_TYPES = {
    "hasCapability": {
        "description": "具备能力",
        "source_type": "OperationalUnit",
        "target_type": "CapabilityProfile",
        "properties": {
            "confidence": {"type": "Number"}
        }
    },
    "hasDeploymentConstraint": {
        "description": "部署约束",
        "source_type": "OperationalUnit",
        "target_type": "DeploymentConstraint",
        "properties": {
            "confidence": {"type": "Number"}
        }
    },
    "suitableOn": {
        "description": "适用环境",
        "source_type": "OperationalUnit",
        "target_type": "PlaceFeature",
        "properties": {
            "note": {"type": "Text", "index": "Text"}
        }
    },
    "constraintRefersTo": {
        "description": "约束涉及",
        "source_type": "DeploymentConstraint",
        "target_type": "PlaceFeature",
        "properties": {
            "aspect": {"type": "Text", "index": "Text"}
        }
    }
}

