//! Small typed accessors over serde_json::Value that error on missing keys.

use anyhow::{Result, anyhow};
use serde_json::Value;

pub fn as_i64(v: &Value) -> Result<i64> {
    v.as_i64().ok_or_else(|| anyhow!("expected int, got {v}"))
}

/// Python `int()` semantics: an int or a numeric string (wire ids sometimes
/// ship as strings).
pub fn as_i64_lenient(v: &Value) -> Result<i64> {
    match v {
        Value::Number(_) => as_i64(v),
        Value::String(s) => crate::util::parse_i64(s),
        other => anyhow::bail!("cannot int() {other:?}"),
    }
}

pub trait ValueExt {
    fn f(&self, key: &str) -> Result<&Value>;
    fn i(&self, key: &str) -> Result<i64>;
    fn s(&self, key: &str) -> Result<&str>;
    fn arr(&self, key: &str) -> Result<&[Value]>;
    fn b(&self, key: &str) -> Result<bool>;
    fn get_i(&self, key: &str) -> Option<i64>;
    fn get_s(&self, key: &str) -> Option<&str>;
    fn get_arr(&self, key: &str) -> Option<&[Value]>;
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
    fn arr(&self, key: &str) -> Result<&[Value]> {
        self.f(key)?
            .as_array()
            .map(Vec::as_slice)
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
    fn get_arr(&self, key: &str) -> Option<&[Value]> {
        self.get(key).and_then(|v| v.as_array()).map(Vec::as_slice)
    }
    fn has(&self, key: &str) -> bool {
        self.get(key).is_some()
    }
}

pub fn int_array(v: &Value) -> Result<Vec<i64>> {
    v.as_array()
        .ok_or_else(|| anyhow!("expected array"))?
        .iter()
        .map(as_i64)
        .collect()
}
