//! Small typed accessors over serde_json::Value with Python-KeyError-like errors.

use anyhow::{Result, anyhow};
use serde_json::Value;

pub fn as_i64(v: &Value) -> Result<i64> {
    v.as_i64().ok_or_else(|| anyhow!("expected int, got {v}"))
}

pub trait ValueExt {
    fn f(&self, key: &str) -> Result<&Value>;
    fn i(&self, key: &str) -> Result<i64>;
    fn s(&self, key: &str) -> Result<&str>;
    fn arr(&self, key: &str) -> Result<&Vec<Value>>;
    fn b(&self, key: &str) -> Result<bool>;
    fn get_i(&self, key: &str) -> Option<i64>;
    fn get_s(&self, key: &str) -> Option<&str>;
    fn get_arr(&self, key: &str) -> Option<&Vec<Value>>;
    fn has(&self, key: &str) -> bool;
}

impl ValueExt for Value {
    fn f(&self, key: &str) -> Result<&Value> {
        self.get(key).ok_or_else(|| anyhow!("KeyError: {key}"))
    }
    fn i(&self, key: &str) -> Result<i64> {
        as_i64(self.f(key)?)
    }
    fn s(&self, key: &str) -> Result<&str> {
        self.f(key)?
            .as_str()
            .ok_or_else(|| anyhow!("expected str at {key}"))
    }
    fn arr(&self, key: &str) -> Result<&Vec<Value>> {
        self.f(key)?
            .as_array()
            .ok_or_else(|| anyhow!("expected array at {key}"))
    }
    fn b(&self, key: &str) -> Result<bool> {
        self.f(key)?
            .as_bool()
            .ok_or_else(|| anyhow!("expected bool at {key}"))
    }
    fn get_i(&self, key: &str) -> Option<i64> {
        self.get(key).and_then(|v| v.as_i64())
    }
    fn get_s(&self, key: &str) -> Option<&str> {
        self.get(key).and_then(|v| v.as_str())
    }
    fn get_arr(&self, key: &str) -> Option<&Vec<Value>> {
        self.get(key).and_then(|v| v.as_array())
    }
    fn has(&self, key: &str) -> bool {
        self.get(key).is_some()
    }
}

/// Python truthiness for a JSON value.
pub fn truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64() != Some(0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

pub fn int_array(v: &Value) -> Result<Vec<i64>> {
    v.as_array()
        .ok_or_else(|| anyhow!("expected array"))?
        .iter()
        .map(as_i64)
        .collect()
}
