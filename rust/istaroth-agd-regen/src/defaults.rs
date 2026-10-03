//! Typed restoration of explicitly declared protobuf defaults.

use anyhow::{Result, anyhow, bail};
use serde_json::Value;

#[derive(Clone, Copy)]
pub(crate) enum FieldDefault {
    Array,
    Bool(bool),
    Int(i64),
    String(&'static str),
}

impl FieldDefault {
    fn value(self) -> Value {
        match self {
            Self::Array => Value::Array(Vec::new()),
            Self::Bool(value) => Value::Bool(value),
            Self::Int(value) => Value::from(value),
            Self::String(value) => Value::String(value.to_string()),
        }
    }

    fn accepts(self, value: &Value) -> bool {
        match self {
            Self::Array => value.is_array(),
            Self::Bool(_) => value.is_boolean(),
            Self::Int(_) => value.as_i64().is_some(),
            Self::String(_) => value.is_string(),
        }
    }
}

/// Return whether the field was explicit, for collection-wide presence checks.
pub(crate) fn apply_field(row: &mut Value, field: &str, default: FieldDefault) -> Result<bool> {
    let object = row
        .as_object_mut()
        .ok_or_else(|| anyhow!("record must be an object"))?;
    if let Some(value) = object.get(field) {
        if !default.accepts(value) {
            bail!("{field} has invalid value {value}");
        }
        Ok(true)
    } else {
        object.insert(field.to_string(), default.value());
        Ok(false)
    }
}

pub(crate) fn apply(row: &mut Value, fields: &[(&str, FieldDefault)]) -> Result<()> {
    for &(field, default) in fields {
        apply_field(row, field, default)?;
    }
    Ok(())
}
