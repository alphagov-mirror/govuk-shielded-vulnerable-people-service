package svp

import io.gatling.core.Predef._
import io.gatling.http.Predef._

import scala.concurrent.duration.FiniteDuration

object ConfigTest {
  val numberOfUsers: Int = System.getProperty("numberOfUsers", "1").toInt
  val duration: FiniteDuration = System.getProperty("durationMinutes", "120").toInt
  val pauseMin: FiniteDuration = System.getProperty("pauseBetweenRequestsInSeconds", "3").toInt
  val pauseMax: FiniteDuration = System.getProperty("pauseBetweenRequestsInSeconds", "5").toInt
  val responseTimeMs = 800
  val responseSuccessPercentage = 99
  val repeatTimes: Int = System.getProperty("numberOfRepetitions", "1").toInt
  private val url: String = System.getProperty("url", "https://gds-shielded-vulnerable-people-service-staging.london.cloudapps.digital")

  val httpProtocol = http
    .baseUrl(url)
    .disableFollowRedirect
    .maxRedirects(1)
    .disableWarmUp
    .disableCaching
    .acceptHeader("text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
    .acceptEncodingHeader("gzip, deflate")
    .acceptLanguageHeader("en-GB,en;q=0.5")
    .userAgentHeader("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:80.0) Gecko/20100101 Firefox/80.0/Gatling")
}
