import { writeReleaseProfile } from './build-release-profile.mjs'

export default async function beforePack() {
  writeReleaseProfile({ env: process.env })
}
