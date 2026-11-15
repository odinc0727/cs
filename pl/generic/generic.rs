// Real Generic
use std::fmt::Display;

fn foo<T: Display>(x: T) {
        println!("{x}");
}

fn main() {
        foo(42);
        foo(69.420);
}
