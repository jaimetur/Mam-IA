plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "app.mamia.android"
    compileSdk = 36   // Google Play asks for target SDK 36

    defaultConfig {
        applicationId = "app.mamia.android"
        minSdk = 28
        targetSdk = 36
        versionCode = (System.getenv("MAMIA_ANDROID_BUILD") ?: "1").toInt()
        // the version of the release (X.Y.Z, set by tools/CreateUpdateRelease.py), the same Google Play shows;
        // versionCode is the CI build number, which Play needs to go up on every upload
        versionName = "0.2.0"
    }

    // in CI, with the keystore in the secrets, the app is signed with it; otherwise with the debug key
    val ks = System.getenv("ANDROID_KEYSTORE_FILE")?.let { file(it) }?.takeIf { it.exists() }
    signingConfigs {
        if (ks != null) create("release") {
            storeFile = ks
            storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("ANDROID_KEY_ALIAS")
            keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName(if (ks != null) "release" else "debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.fragment:fragment-ktx:1.8.5")   // activity results need Fragment 1.3+ (lint)
    implementation("com.android.billingclient:billing-ktx:8.0.0")   // Google Play asks for 8.0.0 or newer   // the subscription in Google Play (Billing.kt)
}
