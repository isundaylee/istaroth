//! Emulation of CPython's set object for non-negative int keys, faithful enough
//! to reproduce iteration order (slot order) — output-visible in a few places
//! (orphaned-dialog listing, waiting-node picks in branch rendering).

const MINSIZE: usize = 8;
const LINEAR_PROBES: usize = 9;
const PERTURB_SHIFT: u32 = 5;

#[derive(Clone)]
pub struct PySet {
    table: Vec<Option<i64>>,
    mask: usize,
    fill: usize,
    used: usize,
}

impl Default for PySet {
    fn default() -> Self {
        Self::new()
    }
}

impl PySet {
    pub fn new() -> Self {
        PySet {
            table: vec![None; MINSIZE],
            mask: MINSIZE - 1,
            fill: 0,
            used: 0,
        }
    }

    fn hash(key: i64) -> u64 {
        debug_assert!(key >= 0);
        // CPython: hash(n) == n for 0 <= n < 2**61 - 1.
        (key as u64) % ((1u64 << 61) - 1)
    }

    pub fn add(&mut self, key: i64) {
        let hash = Self::hash(key);
        let mask = self.mask as u64;
        let mut i = hash & mask;
        let mut perturb = hash;
        let slot = loop {
            let probes = if i as usize + LINEAR_PROBES <= self.mask {
                LINEAR_PROBES
            } else {
                0
            };
            let mut found: Option<u64> = None;
            for j in 0..=probes {
                let idx = (i as usize) + j;
                match self.table[idx] {
                    None => {
                        found = Some(idx as u64);
                        break;
                    }
                    Some(existing) if existing == key => return,
                    Some(_) => {}
                }
            }
            if let Some(idx) = found {
                break idx as usize;
            }
            perturb >>= PERTURB_SHIFT;
            i = (i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb)) & mask;
        };
        self.table[slot] = Some(key);
        self.fill += 1;
        self.used += 1;
        if self.fill * 5 >= self.mask * 3 {
            let minused = if self.used > 50000 {
                self.used * 2
            } else {
                self.used * 4
            };
            self.resize(minused);
        }
    }

    fn resize(&mut self, minused: usize) {
        let mut newsize = MINSIZE;
        while newsize <= minused {
            newsize <<= 1;
        }
        let old = std::mem::replace(&mut self.table, vec![None; newsize]);
        self.mask = newsize - 1;
        for key in old.into_iter().flatten() {
            self.insert_clean(key);
        }
        self.fill = self.used;
    }

    fn insert_clean(&mut self, key: i64) {
        let hash = Self::hash(key);
        let mask = self.mask as u64;
        let mut i = hash & mask;
        let mut perturb = hash;
        loop {
            if self.table[i as usize].is_none() {
                self.table[i as usize] = Some(key);
                return;
            }
            if i as usize + LINEAR_PROBES <= self.mask {
                for j in 1..=LINEAR_PROBES {
                    let idx = i as usize + j;
                    if self.table[idx].is_none() {
                        self.table[idx] = Some(key);
                        return;
                    }
                }
            }
            perturb >>= PERTURB_SHIFT;
            i = (i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb)) & mask;
        }
    }

    /// Iterate keys in table (CPython iteration) order.
    pub fn iter(&self) -> impl Iterator<Item = i64> + '_ {
        self.table.iter().filter_map(|e| *e)
    }

    pub fn from_iter_py(keys: impl IntoIterator<Item = i64>) -> Self {
        let mut s = PySet::new();
        for k in keys {
            s.add(k);
        }
        s
    }

    /// `self - other` with CPython semantics: iterate self in table order,
    /// insert the survivors into a fresh set.
    pub fn difference(&self, other: &rustc_hash::FxHashSet<i64>) -> PySet {
        let mut result = PySet::new();
        for key in self.iter() {
            if !other.contains(&key) {
                result.add(key);
            }
        }
        result
    }

    pub fn len(&self) -> usize {
        self.used
    }

    pub fn is_empty(&self) -> bool {
        self.used == 0
    }
}
