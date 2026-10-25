plugins {
    id("com.android.application")
}

android {
    namespace = "com.markushapper.nerdio"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.markushapper.nerdio"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "0.2.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
}
