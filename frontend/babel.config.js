module.exports = function (api) {
    api.cache(true);
    return {
        presets: [
            ["babel-preset-expo", { jsxImportSource: "nativewind" }],
            "nativewind/babel",
        ],
        plugins: [
            // Reanimated plugin can cause "worklets" resolution error in Jest. 
            // Often it's not strictly needed for basic testing, or should be mocked.
            ...(process.env.NODE_ENV !== "test" ? ["react-native-reanimated/plugin"] : []),
        ],
    };
};
