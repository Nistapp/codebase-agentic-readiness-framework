package com.example.demo;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class AppTest {
    @Test
    void greetsByName() {
        assertEquals("carried-jvm-example-package", App.greeting());
    }
}
