{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/law-output-schema-v2.2.json",
  "title": "Vietnamese Inheritance Fact Extraction Schema v2.2",
  "description": "Compact name-based structural validator.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "case_id",
    "target_decedents",
    "persons",
    "organizations",
    "relationships",
    "estates",
    "wills",
    "inheritance_actions",
    "conduct_events",
    "agreements",
    "events",
    "legal_assertions"
  ],
  "properties": {
    "schema_version": {
      "const": "2.2.0"
    },
    "case_id": {
      "type": [
        "string",
        "null"
      ]
    },
    "target_decedents": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/nonEmptyString"
      },
      "uniqueItems": true
    },
    "persons": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/person"
      }
    },
    "organizations": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/organization"
      }
    },
    "relationships": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/relationship"
      }
    },
    "estates": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/estate"
      }
    },
    "wills": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/will"
      }
    },
    "inheritance_actions": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/inheritanceAction"
      }
    },
    "conduct_events": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/conductEvent"
      }
    },
    "agreements": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/agreement"
      }
    },
    "events": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/event"
      }
    },
    "legal_assertions": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/legalAssertion"
      }
    }
  },
  "$defs": {
    "nonEmptyString": {
      "type": "string",
      "minLength": 1
    },
    "nullableString": {
      "type": [
        "string",
        "null"
      ]
    },
    "time": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^\\d{4}(?:-\\d{2}(?:-\\d{2})?)?$"
        },
        {
          "type": "null"
        }
      ]
    },
    "fraction": {
      "anyOf": [
        {
          "type": "string",
          "pattern": "^(?:\\d+/\\d+|\\d+(?:\\.\\d+)?)$"
        },
        {
          "type": "null"
        }
      ]
    },
    "currency": {
      "anyOf": [
        {
          "enum": [
            "VND",
            "other"
          ]
        },
        {
          "type": "null"
        }
      ]
    },
    "partyType": {
      "enum": [
        "person",
        "organization"
      ]
    },
    "nullablePartyType": {
      "anyOf": [
        {
          "$ref": "#/$defs/partyType"
        },
        {
          "type": "null"
        }
      ]
    },
    "statedFlag": {
      "enum": [
        "stated_true",
        "stated_false",
        "disputed",
        "not_mentioned"
      ]
    },
    "person": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "name",
        "aliases",
        "life_status",
        "death_time",
        "birth_time",
        "conception_time",
        "birth_status",
        "age",
        "age_status",
        "working_capacity",
        "awareness_state",
        "literacy_status",
        "physical_limitation",
        "last_residence"
      ],
      "properties": {
        "name": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "aliases": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/nonEmptyString"
          },
          "uniqueItems": true
        },
        "life_status": {
          "enum": [
            "alive",
            "deceased",
            "unknown"
          ]
        },
        "death_time": {
          "$ref": "#/$defs/time"
        },
        "birth_time": {
          "$ref": "#/$defs/time"
        },
        "conception_time": {
          "$ref": "#/$defs/time"
        },
        "birth_status": {
          "enum": [
            "born_alive",
            "stillborn",
            "unborn",
            "unknown"
          ]
        },
        "age": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        },
        "age_status": {
          "enum": [
            "minor",
            "adult",
            "unknown"
          ]
        },
        "working_capacity": {
          "enum": [
            "able_to_work",
            "unable_to_work",
            "limited_working_capacity",
            "unknown"
          ]
        },
        "awareness_state": {
          "enum": [
            "aware",
            "impaired",
            "unaware",
            "disputed",
            "unknown"
          ]
        },
        "literacy_status": {
          "enum": [
            "literate",
            "illiterate",
            "unknown"
          ]
        },
        "physical_limitation": {
          "$ref": "#/$defs/nullableString"
        },
        "last_residence": {
          "$ref": "#/$defs/nullableString"
        }
      }
    },
    "organization": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "name",
        "organization_type",
        "existence_status",
        "termination_time"
      ],
      "properties": {
        "name": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "organization_type": {
          "enum": [
            "court",
            "enterprise",
            "state_authority",
            "notary_office",
            "commune_committee",
            "hospital",
            "detention_facility",
            "charitable_organization",
            "other"
          ]
        },
        "existence_status": {
          "enum": [
            "existing",
            "not_existing",
            "dissolved",
            "terminated",
            "disputed",
            "unknown"
          ]
        },
        "termination_time": {
          "$ref": "#/$defs/time"
        }
      }
    },
    "relationship": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "subject",
        "relation",
        "object",
        "qualifiers",
        "relationship_status",
        "start_time",
        "end_time",
        "mutual_care"
      ],
      "properties": {
        "subject": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "relation": {
          "enum": [
            "spouse_of",
            "child_of",
            "sibling_of",
            "grandchild_of",
            "great_grandchild_of",
            "grandparent_of",
            "great_grandparent_of",
            "aunt_uncle_of",
            "niece_nephew_of",
            "stepparent_of",
            "other_relative_of"
          ]
        },
        "object": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "qualifiers": {
          "type": "array",
          "items": {
            "enum": [
              "legal_marriage",
              "not_legally_recognized",
              "biological",
              "adopted_legal",
              "adopted_not_legally_recognized",
              "outside_marriage",
              "step_relationship",
              "full_sibling",
              "half_sibling",
              "not_mentioned"
            ]
          },
          "uniqueItems": true
        },
        "relationship_status": {
          "enum": [
            "active",
            "ended",
            "disputed",
            "unknown"
          ]
        },
        "start_time": {
          "$ref": "#/$defs/time"
        },
        "end_time": {
          "$ref": "#/$defs/time"
        },
        "mutual_care": {
          "enum": [
            "stated",
            "absent",
            "disputed",
            "not_mentioned"
          ]
        }
      }
    },
    "owner": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "holder_type",
        "holder",
        "stated_share_ratio"
      ],
      "properties": {
        "holder_type": {
          "$ref": "#/$defs/partyType"
        },
        "holder": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "stated_share_ratio": {
          "$ref": "#/$defs/fraction"
        }
      }
    },
    "asset": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "asset_id",
        "asset_type",
        "description",
        "value",
        "currency",
        "valuation_time",
        "ownership_type",
        "owners",
        "status"
      ],
      "properties": {
        "asset_id": {
          "type": "string",
          "pattern": "^A\\d+$"
        },
        "asset_type": {
          "enum": [
            "cash",
            "house",
            "apartment",
            "land_use_right",
            "vehicle",
            "savings_deposit",
            "gold_jewelry",
            "securities",
            "business_capital",
            "receivable",
            "other"
          ]
        },
        "description": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "value": {
          "type": [
            "integer",
            "number",
            "null"
          ],
          "minimum": 0
        },
        "currency": {
          "$ref": "#/$defs/currency"
        },
        "valuation_time": {
          "$ref": "#/$defs/time"
        },
        "ownership_type": {
          "enum": [
            "separate_property",
            "marital_common_property",
            "joint_property",
            "sole_property",
            "unknown"
          ]
        },
        "owners": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/owner"
          }
        },
        "status": {
          "enum": [
            "existing",
            "partially_existing",
            "sold",
            "transferred",
            "destroyed",
            "recovered",
            "unknown"
          ]
        }
      }
    },
    "obligation": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "obligation_id",
        "obligation_type",
        "creditor_type",
        "creditor",
        "amount",
        "currency",
        "decedent_liability_ratio",
        "secured_asset_ids"
      ],
      "properties": {
        "obligation_id": {
          "type": "string",
          "pattern": "^O\\d+$"
        },
        "obligation_type": {
          "enum": [
            "funeral_expense",
            "unpaid_maintenance",
            "estate_preservation_cost",
            "dependent_support",
            "labor_wage",
            "compensation",
            "tax_or_fee",
            "debt",
            "secured_debt",
            "fine",
            "other"
          ]
        },
        "creditor_type": {
          "enum": [
            "person",
            "organization",
            "unknown"
          ]
        },
        "creditor": {
          "$ref": "#/$defs/nullableString"
        },
        "amount": {
          "type": [
            "integer",
            "number",
            "null"
          ],
          "minimum": 0
        },
        "currency": {
          "$ref": "#/$defs/currency"
        },
        "decedent_liability_ratio": {
          "$ref": "#/$defs/fraction"
        },
        "secured_asset_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^A\\d+$"
          },
          "uniqueItems": true
        }
      }
    },
    "estateRole": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "role",
        "holder_type",
        "holder",
        "appointment_basis",
        "status"
      ],
      "properties": {
        "role": {
          "enum": [
            "estate_manager",
            "estate_distributor",
            "will_custodian",
            "will_publisher",
            "worship_property_manager"
          ]
        },
        "holder_type": {
          "$ref": "#/$defs/partyType"
        },
        "holder": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "appointment_basis": {
          "enum": [
            "will",
            "heir_agreement",
            "current_possession",
            "state_authority",
            "not_mentioned",
            "other"
          ]
        },
        "status": {
          "enum": [
            "active",
            "ended",
            "refused",
            "disputed",
            "unknown"
          ]
        }
      }
    },
    "estate": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "estate_id",
        "decedent",
        "opening_place",
        "assets",
        "obligations",
        "estate_roles",
        "distribution_status"
      ],
      "properties": {
        "estate_id": {
          "type": "string",
          "pattern": "^E\\d+$"
        },
        "decedent": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "opening_place": {
          "$ref": "#/$defs/nullableString"
        },
        "assets": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/asset"
          }
        },
        "obligations": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/obligation"
          }
        },
        "estate_roles": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/estateRole"
          }
        },
        "distribution_status": {
          "enum": [
            "undivided",
            "partially_distributed",
            "fully_distributed",
            "unknown"
          ]
        }
      }
    },
    "authentication": {
      "anyOf": [
        {
          "type": "null"
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "type",
            "place",
            "certifier",
            "time"
          ],
          "properties": {
            "type": {
              "enum": [
                "none",
                "notarized",
                "certified",
                "special_equivalent",
                "unknown"
              ]
            },
            "place": {
              "$ref": "#/$defs/nullableString"
            },
            "certifier": {
              "$ref": "#/$defs/nullableString"
            },
            "time": {
              "$ref": "#/$defs/time"
            }
          }
        }
      ]
    },
    "willFacts": {
      "anyOf": [
        {
          "type": "null"
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "testator_signed",
            "testator_fingerprinted",
            "signed_before_witnesses",
            "witnesses_signed",
            "witness_count",
            "life_threatening_context",
            "unable_to_make_written_will",
            "recorded_immediately",
            "record_time",
            "signature_certification_time",
            "testator_alive_after_three_months",
            "testator_aware_after_three_months",
            "has_execution_date",
            "has_testator_identity",
            "has_beneficiary_identity",
            "has_asset_description",
            "contains_abbreviation_or_symbol",
            "pages_numbered",
            "signed_each_page",
            "has_erasure_or_correction",
            "corrections_countersigned",
            "document_status",
            "content_completeness",
            "ambiguous_content",
            "special_context"
          ],
          "properties": {
            "testator_signed": {
              "$ref": "#/$defs/statedFlag"
            },
            "testator_fingerprinted": {
              "$ref": "#/$defs/statedFlag"
            },
            "signed_before_witnesses": {
              "$ref": "#/$defs/statedFlag"
            },
            "witnesses_signed": {
              "$ref": "#/$defs/statedFlag"
            },
            "witness_count": {
              "type": [
                "integer",
                "null"
              ],
              "minimum": 0
            },
            "life_threatening_context": {
              "$ref": "#/$defs/statedFlag"
            },
            "unable_to_make_written_will": {
              "$ref": "#/$defs/statedFlag"
            },
            "recorded_immediately": {
              "$ref": "#/$defs/statedFlag"
            },
            "record_time": {
              "$ref": "#/$defs/time"
            },
            "signature_certification_time": {
              "$ref": "#/$defs/time"
            },
            "testator_alive_after_three_months": {
              "$ref": "#/$defs/statedFlag"
            },
            "testator_aware_after_three_months": {
              "$ref": "#/$defs/statedFlag"
            },
            "has_execution_date": {
              "$ref": "#/$defs/statedFlag"
            },
            "has_testator_identity": {
              "$ref": "#/$defs/statedFlag"
            },
            "has_beneficiary_identity": {
              "$ref": "#/$defs/statedFlag"
            },
            "has_asset_description": {
              "$ref": "#/$defs/statedFlag"
            },
            "contains_abbreviation_or_symbol": {
              "$ref": "#/$defs/statedFlag"
            },
            "pages_numbered": {
              "$ref": "#/$defs/statedFlag"
            },
            "signed_each_page": {
              "$ref": "#/$defs/statedFlag"
            },
            "has_erasure_or_correction": {
              "$ref": "#/$defs/statedFlag"
            },
            "corrections_countersigned": {
              "$ref": "#/$defs/statedFlag"
            },
            "document_status": {
              "enum": [
                "available",
                "lost",
                "damaged",
                "recovered",
                "destroyed",
                "unknown"
              ]
            },
            "content_completeness": {
              "enum": [
                "complete",
                "partial",
                "unreadable",
                "unknown"
              ]
            },
            "ambiguous_content": {
              "$ref": "#/$defs/statedFlag"
            },
            "special_context": {
              "anyOf": [
                {
                  "enum": [
                    "active_duty_military",
                    "ship",
                    "aircraft",
                    "hospital",
                    "remote_research",
                    "overseas",
                    "detention",
                    "imprisonment",
                    "administrative_facility",
                    "other"
                  ]
                },
                {
                  "type": "null"
                }
              ]
            }
          }
        }
      ]
    },
    "willRelation": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "relation",
        "other_will_id",
        "affected_asset_ids"
      ],
      "properties": {
        "relation": {
          "enum": [
            "amends",
            "supplements",
            "replaces",
            "revokes",
            "partially_revokes",
            "conflicts_with"
          ]
        },
        "other_will_id": {
          "type": "string",
          "pattern": "^W\\d+$"
        },
        "affected_asset_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^A\\d+$"
          },
          "uniqueItems": true
        }
      }
    },
    "disposition": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "disposition_id",
        "disposition_type",
        "recipient_type",
        "recipient",
        "manager_type",
        "manager",
        "affected_persons",
        "scope",
        "asset_ids",
        "share_ratio",
        "amount",
        "currency",
        "condition",
        "appointed_role"
      ],
      "properties": {
        "disposition_id": {
          "type": "string",
          "pattern": "^D\\d+$"
        },
        "disposition_type": {
          "enum": [
            "appoint_heir",
            "bequest",
            "worship_property",
            "disinheritance",
            "impose_obligation",
            "appoint_estate_manager",
            "appoint_estate_distributor",
            "appoint_will_custodian",
            "appoint_will_publisher",
            "other"
          ]
        },
        "recipient_type": {
          "$ref": "#/$defs/nullablePartyType"
        },
        "recipient": {
          "$ref": "#/$defs/nullableString"
        },
        "manager_type": {
          "$ref": "#/$defs/nullablePartyType"
        },
        "manager": {
          "$ref": "#/$defs/nullableString"
        },
        "affected_persons": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/nonEmptyString"
          },
          "uniqueItems": true
        },
        "scope": {
          "enum": [
            "entire_estate",
            "specific_asset",
            "specific_amount",
            "share_ratio",
            "remainder",
            "entire_inheritance_right",
            "other"
          ]
        },
        "asset_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^A\\d+$"
          },
          "uniqueItems": true
        },
        "share_ratio": {
          "$ref": "#/$defs/fraction"
        },
        "amount": {
          "type": [
            "integer",
            "number",
            "null"
          ],
          "minimum": 0
        },
        "currency": {
          "$ref": "#/$defs/currency"
        },
        "condition": {
          "$ref": "#/$defs/nullableString"
        },
        "appointed_role": {
          "$ref": "#/$defs/nullableString"
        }
      }
    },
    "will": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "will_id",
        "testator",
        "date",
        "medium",
        "execution_method",
        "authentication",
        "witnesses",
        "will_facts",
        "relations_to_other_wills",
        "dispositions"
      ],
      "properties": {
        "will_id": {
          "type": "string",
          "pattern": "^W\\d+$"
        },
        "testator": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "date": {
          "$ref": "#/$defs/time"
        },
        "medium": {
          "enum": [
            "written",
            "oral",
            "unknown",
            "other"
          ]
        },
        "execution_method": {
          "enum": [
            "handwritten",
            "typed",
            "written_by_other",
            "oral_declaration",
            "unknown",
            "other"
          ]
        },
        "authentication": {
          "$ref": "#/$defs/authentication"
        },
        "witnesses": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/nonEmptyString"
          },
          "uniqueItems": true
        },
        "will_facts": {
          "$ref": "#/$defs/willFacts"
        },
        "relations_to_other_wills": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/willRelation"
          }
        },
        "dispositions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/disposition"
          }
        }
      }
    },
    "inheritanceAction": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "action_id",
        "person",
        "related_decedent",
        "action",
        "time",
        "form",
        "notified_parties",
        "stated_purpose"
      ],
      "properties": {
        "action_id": {
          "type": "string",
          "pattern": "^IA\\d+$"
        },
        "person": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "related_decedent": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "action": {
          "enum": [
            "renunciation",
            "acceptance",
            "request_distribution",
            "request_postponement",
            "request_redistribution",
            "other"
          ]
        },
        "time": {
          "$ref": "#/$defs/time"
        },
        "form": {
          "enum": [
            "written",
            "oral",
            "unknown",
            "other"
          ]
        },
        "notified_parties": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/nonEmptyString"
          },
          "uniqueItems": true
        },
        "stated_purpose": {
          "$ref": "#/$defs/nullableString"
        }
      }
    },
    "conductEvent": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "conduct_event_id",
        "actor",
        "target",
        "conduct_type",
        "conviction_status",
        "purpose_to_obtain_inheritance",
        "decedent_knew_conduct",
        "decedent_still_granted_by_will"
      ],
      "properties": {
        "conduct_event_id": {
          "type": "string",
          "pattern": "^CE\\d+$"
        },
        "actor": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "target": {
          "$ref": "#/$defs/nullableString"
        },
        "conduct_type": {
          "enum": [
            "intentional_harm_to_decedent",
            "serious_abuse",
            "serious_failure_of_support",
            "intentional_harm_to_other_heir",
            "deception_in_will_making",
            "coercion_in_will_making",
            "obstruction_of_will_making",
            "will_forgery",
            "will_alteration",
            "will_destruction",
            "will_concealment",
            "other"
          ]
        },
        "conviction_status": {
          "enum": [
            "convicted",
            "not_convicted",
            "alleged",
            "disputed",
            "unknown"
          ]
        },
        "purpose_to_obtain_inheritance": {
          "$ref": "#/$defs/statedFlag"
        },
        "decedent_knew_conduct": {
          "$ref": "#/$defs/statedFlag"
        },
        "decedent_still_granted_by_will": {
          "$ref": "#/$defs/statedFlag"
        }
      }
    },
    "agreement": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "agreement_id",
        "agreement_type",
        "participants",
        "form",
        "time",
        "asset_ids",
        "terms"
      ],
      "properties": {
        "agreement_id": {
          "type": "string",
          "pattern": "^AG\\d+$"
        },
        "agreement_type": {
          "enum": [
            "estate_manager_appointment",
            "estate_distributor_appointment",
            "distribution_method",
            "asset_valuation",
            "in_kind_recipient",
            "distribution_postponement",
            "manager_rights_and_duties",
            "manager_remuneration",
            "other"
          ]
        },
        "participants": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/nonEmptyString"
          },
          "uniqueItems": true
        },
        "form": {
          "enum": [
            "written",
            "oral",
            "unknown",
            "other"
          ]
        },
        "time": {
          "$ref": "#/$defs/time"
        },
        "asset_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "pattern": "^A\\d+$"
          },
          "uniqueItems": true
        },
        "terms": {
          "$ref": "#/$defs/nullableString"
        }
      }
    },
    "event": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "event_id",
        "event_type",
        "person",
        "related_person",
        "related_estate_id",
        "related_asset_id",
        "related_will_id",
        "time",
        "temporal_relation",
        "details"
      ],
      "properties": {
        "event_id": {
          "type": "string",
          "pattern": "^EVT\\d+$"
        },
        "event_type": {
          "enum": [
            "declared_missing",
            "declared_dead",
            "death_order",
            "divorce_filed",
            "divorce_decision_issued",
            "divorce_effective",
            "marriage_ended",
            "remarriage",
            "common_property_divided",
            "adoption_started",
            "adoption_ended",
            "asset_sold",
            "asset_transferred",
            "asset_destroyed",
            "asset_recovered",
            "asset_income_generated",
            "will_lost",
            "will_damaged",
            "will_recovered",
            "will_deposited",
            "will_delivered",
            "will_published",
            "will_translated",
            "claim_filed",
            "estate_distributed",
            "distribution_postponed",
            "postponement_extended",
            "new_heir_discovered",
            "heir_right_rejected",
            "refund_requested",
            "compensation_paid",
            "other"
          ]
        },
        "person": {
          "$ref": "#/$defs/nullableString"
        },
        "related_person": {
          "$ref": "#/$defs/nullableString"
        },
        "related_estate_id": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^E\\d+$"
            },
            {
              "type": "null"
            }
          ]
        },
        "related_asset_id": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^A\\d+$"
            },
            {
              "type": "null"
            }
          ]
        },
        "related_will_id": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^W\\d+$"
            },
            {
              "type": "null"
            }
          ]
        },
        "time": {
          "$ref": "#/$defs/time"
        },
        "temporal_relation": {
          "enum": [
            "before",
            "after",
            "same_time",
            "order_indeterminable",
            "not_applicable"
          ]
        },
        "details": {
          "type": "object",
          "additionalProperties": true
        }
      }
    },
    "legalAssertion": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "assertion_id",
        "subject_type",
        "subject_ref",
        "assertion",
        "asserted_by",
        "asserting_party_type",
        "asserting_party"
      ],
      "properties": {
        "assertion_id": {
          "type": "string",
          "pattern": "^LA\\d+$"
        },
        "subject_type": {
          "enum": [
            "person",
            "organization",
            "relationship",
            "asset",
            "obligation",
            "will",
            "inheritance_action",
            "conduct_event",
            "agreement",
            "distribution",
            "other"
          ]
        },
        "subject_ref": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "assertion": {
          "$ref": "#/$defs/nonEmptyString"
        },
        "asserted_by": {
          "enum": [
            "narrative",
            "party_claim",
            "party_denial",
            "party_agreement",
            "court_finding",
            "official_document",
            "other"
          ]
        },
        "asserting_party_type": {
          "$ref": "#/$defs/nullablePartyType"
        },
        "asserting_party": {
          "$ref": "#/$defs/nullableString"
        }
      }
    }
  },
  "x-semantic-validation": [
    "persons[].name must be unique.",
    "organizations[].name must be unique.",
    "Every target_decedents item must exist in persons[].name.",
    "Every person-name reference must exist in persons[].name.",
    "Every organization-name reference must exist in organizations[].name.",
    "Aliases and role labels must not be used as canonical person references.",
    "Technical IDs must be unique within each namespace.",
    "Every referenced estate, asset, will and obligation ID must exist.",
    "Final allocation keys must be a subset of the union of persons[].name and organizations[].name.",
    "Organizations may appear in final allocation as creditors, legatees, or other lawful recipients."
  ]
}
