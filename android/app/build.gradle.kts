plugins {
    id("com.android.application")
}

val nerdioVersionName = System.getenv("NERDIO_VERSION_NAME") ?: "0.2.0"
val nerdioVersionCode = System.getenv("NERDIO_VERSION_CODE")?.toIntOrNull() ?: 2

android {
    namespace = "com.markushapper.nerdio"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.markushapper.nerdio"
        minSdk = 26
        targetSdk = 35
        versionCode = nerdioVersionCode
        versionName = nerdioVersionName
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}
