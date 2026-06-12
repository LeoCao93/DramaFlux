var networkParams = null;

var canonicalSecurityHeaders = {
    "x-argus": "X-Argus",
    "x-gorgon": "X-Gorgon",
    "x-ladon": "X-Ladon",
    "x-khronos": "X-Khronos",
    "x-helios": "X-Helios",
    "x-medusa": "X-Medusa",
    "x-ss-req-ticket": "X-SS-REQ-TICKET"
};

function getNetworkParams() {
    if (networkParams === null) {
        networkParams = Java.use(
            "com.bytedance.frameworks.baselib.network.http.NetworkParams"
        );
    }
    return networkParams;
}

function mapToObject(map) {
    var output = {};
    var iterator = map.keySet().iterator();
    while (iterator.hasNext()) {
        var key = iterator.next();
        var value = map.get(key);
        var text = value === null ? null : value.toString();
        if (
            text &&
            text.charAt(0) === "[" &&
            text.charAt(text.length - 1) === "]"
        ) {
            text = text.substring(1, text.length - 1);
        }
        output[key.toString()] = text;
    }
    return output;
}

function filterSecurityHeaders(headers) {
    var output = {};
    Object.keys(headers).forEach(function (key) {
        var canonical = canonicalSecurityHeaders[key.toLowerCase()];
        if (canonical && headers[key]) {
            output[canonical] = String(headers[key]);
        }
    });
    return output;
}

rpc.exports = {
    health: function () {
        return new Promise(function (resolve, reject) {
            Java.perform(function () {
                try {
                    getNetworkParams();
                    resolve(true);
                } catch (error) {
                    reject(String(error));
                }
            });
        });
    },

    sign: function (url, headersObject) {
        return new Promise(function (resolve, reject) {
            Java.perform(function () {
                try {
                    var HashMap = Java.use("java.util.HashMap");
                    var ArrayList = Java.use("java.util.ArrayList");
                    var headers = HashMap.$new();
                    Object.keys(headersObject).forEach(function (key) {
                        var values = ArrayList.$new();
                        values.add(String(headersObject[key]));
                        headers.put(String(key), values);
                    });
                    var signed = getNetworkParams().tryAddSecurityFactor(
                        String(url),
                        headers
                    );
                    resolve(filterSecurityHeaders(mapToObject(signed)));
                } catch (error) {
                    reject(String(error));
                }
            });
        });
    },

    grab: function (timeoutMs) {
        return new Promise(function (resolve, reject) {
            if (!(timeoutMs > 0)) {
                reject("timeoutMs must be positive");
                return;
            }
            var overload = null;
            var timer = null;
            var completed = false;

            function restoreHook() {
                if (timer !== null) {
                    clearTimeout(timer);
                    timer = null;
                }
                if (overload !== null) {
                    overload.implementation = null;
                }
            }

            Java.perform(function () {
                try {
                    var target = getNetworkParams();
                    overload = target.tryAddSecurityFactor.overload(
                        "java.lang.String",
                        "java.util.Map"
                    );
                    timer = setTimeout(function () {
                        if (!completed) {
                            completed = true;
                            restoreHook();
                            reject("session capture timed out");
                        }
                    }, timeoutMs);
                    overload.implementation = function (url, headers) {
                        try {
                            var result = overload.call(this, url, headers);
                            if (!completed) {
                                var text = String(url);
                                var naturalRequest =
                                    text.indexOf("fqnovel.com") >= 0 &&
                                    text.indexOf("device_id=") >= 0 &&
                                    headers.containsKey("x-ss-req-ticket");
                                if (naturalRequest) {
                                    completed = true;
                                    restoreHook();
                                    resolve({
                                        url: text,
                                        headers: mapToObject(headers)
                                    });
                                }
                            }
                            return result;
                        } catch (error) {
                            if (!completed) {
                                completed = true;
                                restoreHook();
                                reject(String(error));
                            }
                            throw error;
                        }
                    };
                } catch (error) {
                    completed = true;
                    restoreHook();
                    reject(String(error));
                }
            });
        });
    }
};
