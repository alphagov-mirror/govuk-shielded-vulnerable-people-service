package svp

import io.gatling.core.Predef._

class SvpTestSimulation extends Simulation {
  setUp(ShieldedVulnerablePeople.scnEndToEndJourney.inject(atOnceUsers(ConfigTest.numberOfUsers)))
    .protocols(ConfigTest.httpProtocol)
    .maxDuration(ConfigTest.duration * 60)
    .assertions(
      global.responseTime.max.lt(ConfigTest.responseTimeMs),
      global.successfulRequests.percent.gt(ConfigTest.responseSuccessPercentage)
    )
}
